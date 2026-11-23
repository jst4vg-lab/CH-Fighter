"""Run the same redacted security gates locally and in CI."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent


def run(args):
    subprocess.run(args,cwd=ROOT,check=True)


def check_release(folder):
    folder=folder.resolve()
    if not folder.is_dir():
        raise SystemExit('Release folder is missing')
    secrets=[]
    for env in (ROOT/'.env', Path(os.environ.get('CH_DATA_DIR', ROOT/'data'))/'.env',
                Path.home()/'.local/share/clan-hub-crea-manager/.env'):
        if env.is_file():
            for line in env.read_text().splitlines():
                key,sep,value=line.partition('=')
                if sep and any(word in key.upper() for word in ('TOKEN','SECRET','PASSWORD','API_KEY')):
                    value=value.strip().strip('"\'')
                    if len(value)>=8:secrets.append(value.encode())
    forbidden={'.env','app.sqlite','credentials.json','communications-profiles.toml'}
    for file in folder.rglob('*'):
        if file.is_symlink():
            if not file.resolve().is_relative_to(folder):
                raise SystemExit('Release contains an external symlink')
            continue
        if not file.is_file():continue
        if file.name in forbidden or file.name.startswith('.env.') or file.suffix in ('.key','.pem','.p12','.pfx','.sqlite'):
            raise SystemExit(f'Private file in release: {file.relative_to(folder)}')
        with file.open('rb') as stream:
            tail=b''
            while chunk:=stream.read(1024*1024):
                content=tail+chunk
                if any(value in content for value in secrets):
                    raise SystemExit(f'Credential match in release: {file.relative_to(folder)}')
                tail=content[-4096:]
    print('Release privacy check passed')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--release',type=Path)
    args=parser.parse_args()
    scanner=shutil.which('gitleaks') or str(ROOT/'.venv-security/bin/gitleaks')
    audit=shutil.which('pip-audit') or str(ROOT/'.venv-security/bin/pip-audit')
    if not Path(scanner).is_file() or not Path(audit).is_file():
        raise SystemExit('Install Gitleaks 8.30.1 and pip-audit 2.10.1, then add them to PATH')
    run([scanner,'git','--redact','--no-banner','--log-opts=--all','.'])
    with tempfile.TemporaryDirectory(prefix='ch-source-scan-') as temporary:
        names=subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).split(b'\0')
        target=Path(temporary)
        for raw in set(names)-{b''}:
            relative=Path(os.fsdecode(raw))
            source=ROOT/relative
            if source.is_file() and not source.is_symlink():
                (target/relative).parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(source,target/relative)
        run([scanner,'dir','--redact','--no-banner','--config',str(ROOT/'.gitleaks.toml'),temporary])
    run(['npm','audit','--audit-level=high','--ignore-scripts'])
    for requirements in ('requirements-build.lock.txt','requirements-discord-self.lock.txt'):
        run([audit,'-r',requirements,'--disable-pip','--no-deps'])
    if args.release:
        check_release(args.release)
        with tempfile.TemporaryDirectory(prefix='ch-release-rules-') as rules:
            config=Path(rules)/'gitleaks.toml'
            config.write_text('[extend]\nuseDefault = true\n')
            run([scanner,'dir','--redact','--no-banner','--config',str(config),str(args.release)])
    print('Security gates passed')


if __name__=='__main__':
    main()
