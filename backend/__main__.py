import os
import uvicorn

if __name__=='__main__':
    # Loopback is hardcoded: the fixed development identity is not network auth.
    uvicorn.run('backend.app:create_app',factory=True,host='127.0.0.1',port=int(os.environ.get('BMW_PORT','8765')),access_log=False)
