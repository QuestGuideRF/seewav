from pathlib import Path
from setuptools import setup
NAME ='seewav'
DESCRIPTION ='Визуализируйте форму сигнала'
URL ='https://github.com/adefossez/seewav'
EMAIL ='alexandre.defossez@gmail.com'
AUTHOR ='Александр Дефосс'
REQUIRES_PYTHON ='>=3.6.0'
VERSION ="0.1.1a1"
HERE =Path (__file__ ).parent
REQUIRED =[i .strip ()for i in open ("requirements.txt")if i .strip ()]
try :
    with open (HERE /"README.md",encoding ='utf-8')as f :
        long_description ='\n'+f .read ()
except FileNotFoundError :
    long_description =DESCRIPTION
setup (
name =NAME ,
version =VERSION ,
description =DESCRIPTION ,
long_description =long_description ,
long_description_content_type ='text/markdown',
author =AUTHOR ,
author_email =EMAIL ,
python_requires =REQUIRES_PYTHON ,
url =URL ,
py_modules =['seewav'],
entry_points ={
'console_scripts':['seewav=seewav:main'],
},
install_requires =REQUIRED ,
include_package_data =True ,
license ='Нелицензионная лицензия',
classifiers =[
'Тема :: Мультимедиа :: Звук/Аудио',
'Тема :: Мультимедиа :: Видео',
],
)