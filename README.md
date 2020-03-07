# ForwardUnixSocket

This small tool is intended to help use Cygwin/msysgit sockets with the Windows Linux Subsystem.

It was specifically designed to pass SSH keys from the KeeAgent module of KeePass secret management application to the
ssh utility running in the WSL (it only works with Linux sockets.

See [blog post](https://blog.czbix.com/WSL2-KeeAgent.html) for more infomation.

## Release
[Release](https://github.com/CzBiX/ForwardUnixSocket/releases/latest)

## Basic usage
```
ForwardUnixSocket.exe C:\path\to\socket\file.sock
```

You have to check "Public networks", otherwise WSL 2 can't pass firewall.
