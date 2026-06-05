from .oss import OSS


def test_put():
    local = '/home/liang/work/bid/html/1779775906908632.html'
    remote_key = 'html/1779775906908632.html'
    print(OSS.put(local, remote_key))

def test_get():
    local = '/home/liang/work/bid/html/1.html'
    remote_key = 'html/1779775906908632.html'
    print(OSS.get(remote_key, local))