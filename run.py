import os, socket, uvicorn

def free_port(start=8000, end=8010):
    requested=int(os.getenv('AUDITOR_PORT','0') or 0)
    if requested:
        candidates=[requested]
    else:
        candidates=list(range(start,end+1))
    for port in candidates:
        s=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
            s.bind(('127.0.0.1',port)); s.close(); return port
        except OSError:
            s.close()
    raise RuntimeError(f'No free localhost port found in {candidates}')

if __name__ == '__main__':
    port=free_port()
    os.environ['AUDITOR_PORT']=str(port)
    os.environ['AUDITOR_BASE_URL']=f'http://127.0.0.1:{port}'
    print(f'\nAUTONOMOUS UI AUDITOR V14')
    print(f'Dashboard: http://127.0.0.1:{port}')
    print(f'If port 8000 was busy, this run automatically uses {port}.')
    print('Press CTRL+C to stop.\n')
    uvicorn.run('app.main:app',host='127.0.0.1',port=port,reload=False)
