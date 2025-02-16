
#por el momento el programa solo envia cadenas vacias por defecto, varias de las funcionalidades que quiero agregar es el manejo y personalizacion de los paquetes en raw
#quiero agregar ip spoofing
#envio fragmentado de paquetes
#capacidad de coneccion a vpn's 
#lista de puertos por defecto y sus servicios comunes
#captura de respuestas y cabeceras
#debemos implementar el control de tareas por segundo {listo}
#

import __main__
import socket
import argparse
import re
import signal
import sys
import asyncio

#clases personalizadas para conexiones:

#esta clase va a servir para manejar las conexiones udp, para evitar los falsos positivos 

class UDPClientProtocol(asyncio.DatagramProtocol): #esta clase puede ser reutilizada o manejada como modulo fuera de este codigo, se deja aqui para que el mismo sea portable
    def __init__(self):
        self.transport = None
        self.received = asyncio.Future()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        self.received.set_result((data, addr))

    def error_received(self, exc):
        self.received.set_exception(exc)

    def connection_lost(self, exc):
        if not self.received.done():
            self.received.set_result(None)



def cntrl_c(signal_recived, frame):         #esta funcion captura cuando el usuario quiere salir del programa para que no sea una salida abrupta y evitar errores innecesarios
    print('saliendo del Bacala0-Scan')
    sys.exit(0)
signal.signal(signal.SIGINT, cntrl_c)

baner= r"""
 /$$$$$$$                                /$$            /$$$$$$           /$$$$$$                               
| $$__  $$                              | $$           /$$$_  $$         /$$__  $$                              
| $$  \ $$  /$$$$$$   /$$$$$$$  /$$$$$$ | $$  /$$$$$$ | $$$$\ $$        | $$  \__/  /$$$$$$$  /$$$$$$  /$$$$$$$ 
| $$$$$$$  |____  $$ /$$_____/ |____  $$| $$ |____  $$| $$ $$ $$ /$$$$$$|  $$$$$$  /$$_____/ |____  $$| $$__  $$
| $$__  $$  /$$$$$$$| $$        /$$$$$$$| $$  /$$$$$$$| $$\ $$$$|______/ \____  $$| $$        /$$$$$$$| $$  \ $$
| $$  \ $$ /$$__  $$| $$       /$$__  $$| $$ /$$__  $$| $$ \ $$$         /$$  \ $$| $$       /$$__  $$| $$  | $$
| $$$$$$$/|  $$$$$$$|  $$$$$$$|  $$$$$$$| $$|  $$$$$$$|  $$$$$$/        |  $$$$$$/|  $$$$$$$|  $$$$$$$| $$  | $$
|_______/  \_______/ \_______/ \_______/|__/ \_______/ \______/          \______/  \_______/ \_______/|__/  |__/
                                                                                             desarrollado por mike aka.Bacala0                                                                                           
"""
print ('\033[1;35m'+ baner +'\033[0m')

##esta es la funcion para conectarnos mediante TCP e ipv4 (falta agregar la deteccion de puertos)

async def connect_tcp(ip, port, semaforo):            #esta funcion a sido modificada para manejar conexiones multiples, donde cada tarea tendra un tiempo de 2 seg
    count=0
    async with semaforo:
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(ip, port),
                timeout=2
            )
            writer.write(b'')
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            print(f'puerto {port} abierto')
            count-=1
        except Exception:
            count+=1
        return count
            

#esta es la funcion para conectarnos mediante UDP e ipv4 (la funcion mostrara si hay o no respuesta, ademas de que si esta cerrado (lo que nos da una posibilidad de ver puertos filtrados))
async def connect_udp(ip, port, semaforo):
    count=0
    async with semaforo:
        try:
            loop = asyncio.get_event_loop()
            transport, protocol = await loop.create_datagram_endpoint(lambda: UDPClientProtocol(), remote_addr=(ip, port))

            transport.sendto(b'')
            try:
                await asyncio.wait_for(protocol.received, timeout=2)
                print(f'puerto {port} abierto')
                count -= 1
            except asyncio.TimeoutError:
                print(f'el puerto {port} puede estar filtrado')
            transport.close()
        except Exception:
            count += 1
    return count
            

#esta es la funcion que va a crear las tareas basandose en loas argumentos recibidos para pasarselos a la funcion de coneccion

async def tareas(ip, ports, semaforo, delay, protocol):
        if protocol == 'tcp':
            tasks=[]
            for port in ports:
                tasks.append(asyncio.create_task(connect_tcp(ip, port, semaforo)))
                await asyncio.sleep(delay)
            resultados = await asyncio.gather(*tasks)
            total_errores= sum(resultados)
            print(f'{total_errores} puertos no conectados')

        else:
            tasks=[]
            for port in ports:
                tasks.append(asyncio.create_task(connect_udp(ip, port, semaforo)))
                await asyncio.sleep(delay)
            resultados = await asyncio.gather(*tasks)
            total_errores= sum(resultados)
            print(f'{total_errores} puertos no conectados')            




#esta es la funcion principal que va a recibir y gestionar los parametros que le demos al programa
async def main():
    parser = argparse.ArgumentParser(description='Simple herramienta de escaneo de puertos')
    parser.add_argument('-i', dest='ip', type=str, required=True, help='Dirección IP del servidor')
    parser.add_argument('-p', dest='port', type=str, required=True, help='Puerto del servidor o un rango de puertos')
    parser.add_argument('-P', dest='protocol', type=str, choices=['tcp', 'udp'], default='tcp', help='Protocolo de conexión (tcp o udp)')
    parser.add_argument('-c', dest='conexiones', type=int, default=10, help='Cuantas conexiones que se iniciaran por segundo')
    parser.add_argument('-max', dest='concurrentes', type=int, default=20, help='Conexiones simultaneas maximas !muchas pueden derivar en un dos o bloqueos')

    args = parser.parse_args()                                      ##esto es importante, porque parseara los argumentos para que puedan ser usados en el codigo
    semaforo = asyncio.Semaphore(args.concurrentes)
    delay =1 /args.conexiones
        
    port_range = re.match(r'(\d+)-(\d+)', args.port)                    #esto va a verificar si el parametro -p es un rango de puertos o solo un puerto individual (luego se pondremos mas condiciones para mas funciones futuras)
    if port_range:
        start_port, end_port = int(port_range.group(1)), int(port_range.group(2))       #aqui, el condicional le da valor a la variable ports antes de pasarla como argumento a la conecion socket
        ports = range(start_port, end_port +1)

    else:
        ports=[int(args.port)]                                                      #en caso de que no se cumple la condicion del if, el valor sera el indicado en la terminal

                                                                            #este condicional hara que se ejecuten tareas en paralelo por cada puerto pero en una  misma conexion socket
    if args.protocol == 'tcp':                                                  #si el argumento "protocolo" mantiene su valor por defecto, la conexion sera por tcp
        await tareas(args.ip, ports, semaforo, delay, args.protocol)

    elif args.protocol == 'udp':                                                  #de lo contrario, la conexion sera UDP (aun debemos arreglar esta funcion para trabajar con async)
        await tareas(args.ip, ports, semaforo, delay, args.protocol) 

    await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()})
   


if __name__ == '__main__':
    asyncio.run(main())
