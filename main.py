#!/usr/bin/env python3
import socket
import ssl
from bs4 import BeautifulSoup

from icecream import ic

class HTTPSocket:
    '''
    '''
    BLOCK_SZ = 4096

    def __init__(self, host, sock=None):
        self.host = host
        if sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        else:
            self.sock = sock
        context = ssl.create_default_context()
        self.sock = context.wrap_socket(self.sock, server_hostname=host)

        self.sock.connect((host, 443))


    def request(self):
        request = "GET / HTTP/1.1\r\nHost: {}\r\n\r\n".format(self.host)
        self.sock.sendall(request.encode())

        data = b''
        bytes_recd = 0
        # receive the entire headers
        while True:
            chunk = self.sock.recv(self.BLOCK_SZ)
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            data += chunk
            bytes_recd = bytes_recd + len(chunk)
            if b'\r\n\r\n' in chunk:  # Check for end of headers
                break

        end = data.find(b'\r\n\r\n')
        headers = [l.split(maxsplit=1) for l in data[:end].split(b'\r\n')]

        chunked = False
        content_len = -1
        for name, val in headers:
            if name == b'Content-Length:':
                content_len = int(val.decode())
                break
        else:
            if not [b'Transfer-Encoding:', b'chunked'] in headers:
                raise RuntimeError("No 'Content-Length' in the HTTP response, and not chunked.")
            chunked = True

        charset = 'utf-8'
        for name, val in headers:
            if name == b'Content-Type:' and b'charset' in val:
                charset = val[val.find(b'charset=')+len('charset='):].decode()
                break


        if chunked:
            buf = data[end+4:]
            content = b''

            # assuming we've recv'd at least the first chunk length already
            while True:
                crlf = buf.find(b'\r\n')
                if crlf == -1:
                    break

                num_str = buf[:crlf]
                chunk_len = int(num_str, 16)
                buf = buf[crlf+2:]

                if chunk_len == 0:
                    break

                while chunk_len+2+3 > len(buf):
                    chunk = self.sock.recv(self.BLOCK_SZ)
                    if chunk == b'':
                        raise RuntimeError("socket connection broken")
                    buf += chunk

                content += buf[:chunk_len]
                buf = buf[chunk_len+2:]

        else:
            content = data[end+4:]
            while len(content) < content_len:
                sz = min(self.BLOCK_SZ, content_len - len(content))
                chunk = self.sock.recv(sz)
                if chunk == b'':
                    raise RuntimeError("socket connection broken")
                content += chunk

        return content.decode(charset)


s = HTTPSocket('search.marginalia.nu')
resp = s.request()
soup = BeautifulSoup(resp, 'html.parser')

print(soup.get_text())
