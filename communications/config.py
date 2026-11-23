"""Backend-only environment loading; never serialize this mapping to clients."""
import os
from crea_core import ROOT

def load_environment():
    values={}
    roots=[os.path.join(str(ROOT),'.env'),os.path.join(os.environ.get('CH_DATA_DIR',os.path.join(str(ROOT),'data')),'.env')]
    for path in roots:
      if not os.path.isfile(path):continue
      with open(path,encoding='utf-8') as stream:
        for line in stream:
            line=line.strip()
            if line and not line.startswith('#') and '=' in line:
                key,value=line.split('=',1); values[key.strip()]=value.strip().strip('"\'')
    values.update(os.environ)
    return values


