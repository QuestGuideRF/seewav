import argparse
import json
import math
import subprocess as sp
import sys
import tempfile
from pathlib import Path
import cairo
import numpy as np
import tqdm
_is_main =False
def colorize (text ,color ):
    code =f"\033[{color }m"
    restore ="\033[0m"
    return "".join ([code ,text ,restore ])
def fatal (msg ):
    if _is_main :
        head ="error: "
        if sys .stderr .isatty ():
            head =colorize ("error: ",1 )
        print (head +str (msg ),file =sys .stderr )
        sys .exit (1 )
def read_info (media ):
    proc =sp .run ([
    'ffprobe',"-loglevel","panic",
    str (media ),'-print_format','json','-show_format','-show_streams'
    ],
    capture_output =True )
    if proc .returncode :
        raise IOError (f"{media } does not exist or is of a wrong type.")
    return json .loads (proc .stdout .decode ('utf-8'))
def read_audio (audio ,seek =None ,duration =None ):
    info =read_info (audio )
    channels =None
    stream =info ['streams'][0 ]
    if stream ["codec_type"]!="audio":
        raise ValueError (f"{audio } should contain only audio.")
    channels =stream ['channels']
    samplerate =float (stream ['sample_rate'])
    command =['ffmpeg','-y']
    command +=['-loglevel','panic']
    if seek is not None :
        command +=['-ss',str (seek )]
    command +=['-i',audio ]
    if duration is not None :
        command +=['-t',str (duration )]
    command +=['-f','f32le']
    command +=['-']
    proc =sp .run (command ,check =True ,capture_output =True )
    wav =np .frombuffer (proc .stdout ,dtype =np .float32 )
    return wav .reshape (-1 ,channels ).T ,samplerate
def sigmoid (x ):
    return 1 /(1 +np .exp (-x ))
def envelope (wav ,window ,stride ):
    wav =np .pad (wav ,window //2 )
    out =[]
    for off in range (0 ,len (wav )-window ,stride ):
        frame =wav [off :off +window ]
        out .append (np .maximum (frame ,0 ).mean ())
    out =np .array (out )
    out =1.9 *(sigmoid (2.5 *out )-0.5 )
    return out
def draw_env (envs ,out ,fg_colors ,bg_color ,size ):
    surface =cairo .ImageSurface (cairo .FORMAT_ARGB32 ,*size )
    ctx =cairo .Context (surface )
    ctx .scale (*size )
    ctx .set_source_rgb (*bg_color )
    ctx .rectangle (0 ,0 ,1 ,1 )
    ctx .fill ()
    K =len (envs )
    T =len (envs [0 ])
    pad_ratio =0.1
    width =1. /(T *(1 +2 *pad_ratio ))
    pad =pad_ratio *width
    delta =2 *pad +width
    ctx .set_line_width (width )
    for step in range (T ):
        for i in range (K ):
            half =0.5 *envs [i ][step ]
            half /=K
            midrule =(1 +2 *i )/(2 *K )
            ctx .set_source_rgb (*fg_colors [i ])
            ctx .move_to (pad +step *delta ,midrule -half )
            ctx .line_to (pad +step *delta ,midrule )
            ctx .stroke ()
            ctx .set_source_rgba (*fg_colors [i ],0.8 )
            ctx .move_to (pad +step *delta ,midrule )
            ctx .line_to (pad +step *delta ,midrule +0.9 *half )
            ctx .stroke ()
    surface .write_to_png (out )
def interpole (x1 ,y1 ,x2 ,y2 ,x ):
    return y1 +(y2 -y1 )*(x -x1 )/(x2 -x1 )
def visualize (audio ,
tmp ,
out ,
seek =None ,
duration =None ,
rate =60 ,
bars =50 ,
speed =4 ,
time =0.4 ,
oversample =3 ,
fg_color =(.2 ,.2 ,.2 ),
fg_color2 =(.5 ,.3 ,.6 ),
bg_color =(1 ,1 ,1 ),
size =(400 ,400 ),
stereo =False ,
):
    try :
        wav ,sr =read_audio (audio ,seek =seek ,duration =duration )
    except (IOError ,ValueError )as err :
        fatal (err )
        raise
    wavs =[]
    if stereo :
        assert wav .shape [0 ]==2 ,'для стерео требуется стерео аудиофайл'
        wavs .append (wav [0 ])
        wavs .append (wav [1 ])
    else :
        wav =wav .mean (0 )
        wavs .append (wav )
    for i ,wav in enumerate (wavs ):
        wavs [i ]=wav /wav .std ()
    window =int (sr *time /bars )
    stride =int (window /oversample )
    envs =[]
    for wav in wavs :
        env =envelope (wav ,window ,stride )
        env =np .pad (env ,(bars //2 ,2 *bars ))
        envs .append (env )
    duration =len (wavs [0 ])/sr
    frames =int (rate *duration )
    smooth =np .hanning (bars )
    print ("Генерация кадров...")
    for idx in tqdm .tqdm (range (frames ),unit =" frames",ncols =80 ):
        pos =(((idx /rate ))*sr )/stride /bars
        off =int (pos )
        loc =pos -off
        denvs =[]
        for env in envs :
            env1 =env [off *bars :(off +1 )*bars ]
            env2 =env [(off +1 )*bars :(off +2 )*bars ]
            maxvol =math .log10 (1e-4 +env2 .max ())*10
            speedup =np .clip (interpole (-6 ,0.5 ,0 ,2 ,maxvol ),0.5 ,2 )
            w =sigmoid (speed *speedup *(loc -0.5 ))
            denv =(1 -w )*env1 +w *env2
            denv *=smooth
            denvs .append (denv )
        draw_env (denvs ,tmp /f"{idx :06d}.png",(fg_color ,fg_color2 ),bg_color ,size )
    audio_cmd =[]
    if seek is not None :
        audio_cmd +=["-ss",str (seek )]
    audio_cmd +=["-i",audio .resolve ()]
    if duration is not None :
        audio_cmd +=["-t",str (duration )]
    print ("Кодирование анимационного видео... ")
    sp .run ([
    "ffmpeg","-y","-loglevel","panic","-r",
    str (rate ),"-f","image2","-s",f"{size [0 ]}x{size [1 ]}","-i","%06d.png"
    ]+audio_cmd +[
    "-c:a","aac","-vcodec","libx264","-crf","10","-pix_fmt","yuv420p",
    out .resolve ()
    ],
    check =True ,
    cwd =tmp )
def parse_color (colorstr ):
    try :
        r ,g ,b =[float (i )for i in colorstr .split (",")]
        return r ,g ,b
    except ValueError :
        fatal ("Формат цвета — 3 числа с плавающей запятой, разделенные запятыми: 0.xx,0.xx,0.xx, порядок RGB.")
        raise
def main ():
    parser =argparse .ArgumentParser (
    'seewav',description ="Создайте красивую анимацию в формате mp4 из аудиофайла.")
    parser .add_argument ("-r","--rate",type =int ,default =60 ,help ="Частота кадров видео.")
    parser .add_argument ("--stereo",action ='store_true',
    help ="Создайте 2 формы волны для стереофайлов.")
    parser .add_argument ("-c",
    "--color",
    default =[0.03 ,0.6 ,0.3 ],
    type =parse_color ,
    dest ="color",
    help ="Цвет столбцов как `r,g,b` в [0, 1].")
    parser .add_argument ("-c2",
    "--color2",
    default =[0.5 ,0.3 ,0.6 ],
    type =parse_color ,
    dest ="color2",
    help ="Цвет второго сигнала как «r,g,b» в [0, 1] (для стерео).")
    parser .add_argument ("--white",action ="store_true",
    help ="Используйте белый фон. По умолчанию черный.")
    parser .add_argument ("-B",
    "--bars",
    type =int ,
    default =50 ,
    help ="Количество полос в видео одновременно")
    parser .add_argument ("-O","--oversample",type =float ,default =4 ,
    help ="Более низкие значения будут ощущаться менее реактивными.")
    parser .add_argument ("-T","--time",type =float ,default =0.4 ,
    help ="Количество звука, отображаемого одновременно в кадре.")
    parser .add_argument ("-S","--speed",type =float ,default =4 ,
    help ="Более высокие значения означают более быстрые переходы между кадрами.")
    parser .add_argument ("-W",
    "--width",
    type =int ,
    default =480 ,
    help ="ширина анимации в пикселях")
    parser .add_argument ("-H",
    "--height",
    type =int ,
    default =300 ,
    help ="высота анимации в пикселях")
    parser .add_argument ("-s","--seek",type =float ,help ="Ищите время в секундах в видео.")
    parser .add_argument ("-d","--duration",type =float ,help ="Продолжительность в секундах от времени поиска.")
    parser .add_argument ("audio",type =Path ,help ='Путь к аудиофайлу')
    parser .add_argument ("out",
    type =Path ,
    nargs ='?',
    default =Path ('out.mp4'),
    help ='Путь к выходному файлу. По умолчанию — ./out.mp4.')
    args =parser .parse_args ()
    with tempfile .TemporaryDirectory ()as tmp :
        visualize (args .audio ,
        Path (tmp ),
        args .out ,
        seek =args .seek ,
        duration =args .duration ,
        rate =args .rate ,
        bars =args .bars ,
        speed =args .speed ,
        oversample =args .oversample ,
        time =args .time ,
        fg_color =args .color ,
        fg_color2 =args .color2 ,
        bg_color =[1. *bool (args .white )]*3 ,
        size =(args .width ,args .height ),
        stereo =args .stereo )
if __name__ =="__main__":
    _is_main =True
    main ()