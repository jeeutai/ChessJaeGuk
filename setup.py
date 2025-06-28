from cx_Freeze import setup, Executable

buildOptions = dict(packages = ['os', 'itertools','zipfile','winsound','time','datetime','flask','random','csv','logging','werkzeug.middleware.proxy_fix','functools','jsom'])

exe = [Executable('main.py')] 
setup(
    name='FindPassword',
    version='0.0.1',
    description='FindPassword',
    options=dict(build_exe=buildOptions),
    executables=exe )