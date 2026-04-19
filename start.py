import os
import sys

os.environ['LC_ALL'] = 'zh_CN.UTF-8'
os.environ['LANG'] = 'zh_CN.UTF-8'
os.environ['LC_CTYPE'] = 'zh_CN.UTF-8'
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

import uvicorn

if __name__ == '__main__':
    uvicorn.run('app:app', host='0.0.0.0', port=8000, reload=True)