import socket

import pytest


@pytest.fixture(autouse=True)
def prohibit_external_network(monkeypatch):
    """Mocks and in-process clients are required; loopback supports local fixtures."""
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_getaddrinfo = socket.getaddrinfo

    def guarded_connect(connection, address):
        if isinstance(address, tuple) and address[0] not in {'127.0.0.1', '::1', 'localhost'}:
            pytest.fail(f'External network access is forbidden in tests: {address[0]}')
        return original_connect(connection, address)

    def guarded_connect_ex(connection, address):
        if isinstance(address, tuple) and address[0] not in {'127.0.0.1', '::1', 'localhost'}:
            pytest.fail(f'External network access is forbidden in tests: {address[0]}')
        return original_connect_ex(connection, address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        if host not in {None, '127.0.0.1', '::1', 'localhost'}:
            pytest.fail(f'External DNS resolution is forbidden in tests: {host}')
        return original_getaddrinfo(host, *args, **kwargs)

    monkeypatch.setattr(socket.socket, 'connect', guarded_connect)
    monkeypatch.setattr(socket.socket, 'connect_ex', guarded_connect_ex)
    monkeypatch.setattr(socket, 'getaddrinfo', guarded_getaddrinfo)
