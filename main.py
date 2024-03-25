#!/usr/bin/env python3
import socket
import ssl
from bs4 import BeautifulSoup
from urllib.parse import urlparse

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

    def _get_remaining_bytes(self, data, content_len):
        '''Once you have received all the headers,
        you will either know the length of the content by the Content-Length,
        or it will be chunked.
        This method takes the partial data received after the headers, and fetches the rest.'''
        while len(data) < content_len:
            sz = min(self.BLOCK_SZ, content_len - len(data))
            chunk = self.sock.recv(sz)
            if chunk == b'':
                raise RuntimeError("socket connection broken")
            data += chunk
        return data

    def _get_remaining_bytes_chunked(self, data):
        '''This method takes the partial data received after the headers,
        and fetches the rest, considering the content is chunked.'''
        content = b''

        # assuming we've recv'd at least the first chunk length already
        while True:
            crlf = data.find(b'\r\n')
            if crlf == -1:
                break

            num_str = data[:crlf]
            chunk_len = int(num_str, 16)
            data = data[crlf+2:]

            if chunk_len == 0:
                break

            while chunk_len+2+3 > len(data):  # 2 for \r\f, 3 for the potential \0\r\f
                chunk = self.sock.recv(self.BLOCK_SZ)
                if chunk == b'':
                    raise RuntimeError("socket connection broken")
                data += chunk

            content += data[:chunk_len]
            data = data[chunk_len+2:]
        return content

    def request(self, url):
        parsed_url = urlparse(url)
        path = parsed_url.path or '/'
        query_string = parsed_url.query

        request = f"GET {path}?{query_string} HTTP/1.1\r\nHost: {self.host}\r\n\r\n"
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
        ic(headers)
        data = data[end+4:]

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

        content = self._get_remaining_bytes_chunked(data) if chunked\
            else self._get_remaining_bytes(data, content_len)

        charset = 'utf-8'
        for name, val in headers:
            if name == b'Content-Type:' and b'charset' in val:
                charset = val[val.find(b'charset=')+len('charset='):].decode()
                break
        return content.decode(charset)



# host = 'marginalia.nu'   # redirect
# host = 'example.com'

host = 'search.marginalia.nu'
s = HTTPSocket(host)
resp = s.request('https://search.marginalia.nu/search?query=art')

soup = BeautifulSoup(resp, 'html.parser')
print(soup.get_text())
