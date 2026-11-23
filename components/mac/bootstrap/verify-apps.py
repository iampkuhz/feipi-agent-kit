#!/usr/bin/env python3
"""在新 Mac 上真实验证浏览器/PDF、Office 转换与 JDK；日志和产物留在私有状态目录。"""
import datetime
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import tempfile


def main():
    if platform.system() != 'Darwin':
        raise SystemExit('该验收仅适用于 macOS。')
    os.umask(0o077)
    root = Path(__file__).resolve().parents[3]
    state = Path.home()/'.local/state/feipi-workbench/validation'
    state.mkdir(parents=True, exist_ok=True)
    artifacts = Path(tempfile.mkdtemp(prefix='mac-apps-', dir=state))
    report = {'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'macos': platform.mac_ver()[0], 'architecture': platform.machine(),
              'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), 'checks': {}}

    def command(name, args, env=None):
        process = subprocess.Popen([str(arg) for arg in args], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True, env=env)
        try:
            output, errors = process.communicate(timeout=180)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGTERM)
            try:
                output, errors = process.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                output, errors = process.communicate()
            (artifacts/(name+'.log')).write_bytes(output+b'\n'+errors)
            raise
        (artifacts/(name+'.log')).write_bytes(output+b'\n'+errors)
        if process.returncode:
            raise RuntimeError(f'{name} 失败，退出码 {process.returncode}')
        return output.decode('utf-8', errors='replace').strip()

    def stage(name, task):
        try:
            task()
            report['checks'][name] = {'passed': True}
            print('[通过] '+name, flush=True)
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
            report['checks'][name] = {'passed': False, 'error': str(error)}
            print('[失败] '+name+'：'+str(error), flush=True)

    html = artifacts/'sample.html'
    html.write_text('<!doctype html><html lang="zh-CN"><head><meta http-equiv="Content-Type" content="text/html; charset=utf-8">'
                    '<title>New Mac validation</title><style>'
                    'body { font-family: "Noto Sans CJK SC", sans-serif; color: #000; }'
                    '</style></head><body><font face="Noto Sans CJK SC"><h1>New Mac validation</h1>'
                    '<p>新机器文档转换与浏览器验收。</p></font></body></html>', encoding='utf-8')

    def inspect_pdf(name, path, chinese_fonts):
        if not path.is_file() or path.stat().st_size < 100:
            raise RuntimeError('没有生成有效 PDF：'+path.name)
        text = command(name+'-text', ['pdftotext', path, '-'])
        if 'New Mac validation' not in text or '新机器文档转换与浏览器验收。' not in text:
            raise RuntimeError('PDF 未包含完整中英文验收正文')
        fonts = command(name+'-fonts', ['pdffonts', path])
        embedded = {fields[0] for line in fonts.splitlines()[2:]
                    if len(fields := line.split()) >= 6 and fields[-5] == 'yes'}
        if not any(font in family for family in embedded for font in chinese_fonts):
            raise RuntimeError('PDF 未嵌入所需的中文字体')
        command(name+'-render', ['pdftoppm', '-f', '1', '-singlefile', '-scale-to', '1000', '-png', path, artifacts/name])
        if not (artifacts/(name+'.png')).is_file():
            raise RuntimeError('PDF 渲染未生成 PNG')

    def browser():
        program = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
        report['chrome_version'] = command('chrome-version', [program, '--version'])
        output = artifacts/'chrome.pdf'
        command('chrome-export', [program, '--headless=new', '--disable-gpu', '--no-first-run',
                                 '--no-default-browser-check', '--disable-background-networking',
                                 '--disable-component-update', '--metrics-recording-only',
                                 '--user-data-dir='+str(artifacts/'chrome-profile'),
                                 '--print-to-pdf='+str(output), html.as_uri()])
        inspect_pdf('chrome', output, ('NotoSansCJKsc', 'PingFangSC'))

    def office():
        program = '/Applications/LibreOffice.app/Contents/MacOS/soffice'
        # 非交互验收不加载 .zshrc；采用终端配置相同的本机 Fontconfig 默认值。
        environment = dict(os.environ)
        if not environment.get('FONTCONFIG_FILE'):
            for candidate in ('/opt/homebrew/etc/fonts/fonts.conf', '/usr/local/etc/fonts/fonts.conf'):
                if Path(candidate).is_file():
                    environment['FONTCONFIG_FILE'] = candidate
                    break
            else:
                raise RuntimeError('缺少 Homebrew fontconfig 的 fonts.conf')
        report['fontconfig_file'] = environment['FONTCONFIG_FILE']
        report['libreoffice_version'] = command('office-version', [program, '--version'])
        command('office-export', [program, '-env:UserInstallation='+(artifacts/'office-profile').as_uri(),
                                 '--headless', '--convert-to', 'pdf', '--outdir', artifacts, html], env=environment)
        inspect_pdf('office', artifacts/'sample.pdf', ('NotoSansCJKsc',))

    def java():
        java_home = Path(command('java-home', ['/usr/libexec/java_home', '-v', '25']))
        version = command('javac-version', [java_home/'bin/javac', '-version'])
        if not version.startswith('javac 25.'):
            raise RuntimeError('需要 JDK 25，实际为 '+version)
        report['javac_version'] = version
        source = artifacts/'NewMacCheck.java'
        source.write_text('public class NewMacCheck { public static void main(String[] args) {'
                          'System.out.println("new-mac-java-ok"); } }\n')
        command('javac', [java_home/'bin/javac', '-d', artifacts, source])
        if command('java-run', [java_home/'bin/java', '-cp', artifacts, 'NewMacCheck']) != 'new-mac-java-ok':
            raise RuntimeError('Java 程序输出不符')

    try:
        report['source_commit'] = command('source', ['git', '-C', root, 'rev-parse', 'HEAD'])
        report['source_dirty'] = bool(command('source-status', ['git', '-C', root, 'status', '--porcelain',
                                      '--untracked-files=normal', '--', 'components/mac', 'scripts/workbench/main.py']))
        stage('Chrome 导出 PDF 与渲染', browser)
        stage('LibreOffice 转换 PDF 与渲染', office)
        stage('JDK 25 编译与执行', java)
    finally:
        (artifacts/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
        print('验收日志与产物：'+str(artifacts), flush=True)
    if len(report['checks']) != 3 or not all(item['passed'] for item in report['checks'].values()):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
