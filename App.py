import streamlit as st
import yt_dlp
import os
import tempfile
import shutil
import zipfile
import glob
import re

st.set_page_config(page_title="YouTube MP3 Downloader", page_icon="🎵")

st.title("🎵 YouTube to MP3 Downloader")
st.write("Vlož odkaz na video nebo celý playlist a stáhni si audio ve formátu MP3.")

# Vstup pro URL
url = st.text_input("Vlož YouTube URL (video nebo playlist):", placeholder="https://www.youtube.com/...")

# Pomocná funkce pro bezpečný název souboru
def safe_filename(s: str) -> str:
    s = s.strip()
    # Odstranění nebezpečných znaků pro souborové systémy
    s = re.sub(r'[\\/*?:"<>|]', "_", s)
    # Oříznout příliš dlouhé názvy (volitelně)
    return s[:200]

def check_ffmpeg_installed():
    return shutil.which("ffmpeg") is not None

def download_audio_to_tmp(link: str, bitrate: str = "192") -> tuple:
    """
    Stáhne buď jedno video nebo celý playlist do dočasného adresáře.
    Vrací (path_to_result_file, display_name, is_zip_flag).
    """
    if not check_ffmpeg_installed():
        raise RuntimeError("ffmpeg není nainstalován nebo není dostupný v PATH. Nainstaluj ffmpeg a zkuste to znovu.")

    tmpdir = tempfile.mkdtemp(prefix="ytmp3_")
    try:
        # Uložíme audio soubory přímo do tmpdir
        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tmpdir, "%(title)s.%(ext)s"),
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": bitrate,
                }
            ],
            # Ticho vypnuto, ale můžeme přidat progress hook níže
            "quiet": True,
            "no_warnings": True,
            # zachovat metadata názvů bez složek
            "restrictfilenames": False,
        }

        # jednoduchý progress hook (Streamlit progress zobrazíme v UI volající funkce)
        downloaded_files_before = set(os.listdir(tmpdir))
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)

        # Najdeme nově vytvořené mp3 soubory v tmpdir
        mp3_files = sorted(glob.glob(os.path.join(tmpdir, "*.mp3")))

        if not mp3_files:
            raise RuntimeError("Stahování proběhlo, ale žádné MP3 soubory nebyly nalezeny.")

        # Pokud jde o playlist (více souborů), vytvoříme ZIP
        if len(mp3_files) > 1 or info.get("_type") == "playlist":
            # Bezpečný základní název pro ZIP
            playlist_title = info.get("title") or "playlist"
            zip_name = safe_filename(playlist_title) + ".zip"
            zip_path = os.path.join(tmpdir, zip_name)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for i, fpath in enumerate(mp3_files, start=1):
                    # Přejmenujeme ve ZIPu soubory aby byly v přehledném pořadí a bezpečné
                    base = os.path.basename(fpath)
                    safe_base = safe_filename(base)
                    arcname = f"{i:03d} - {safe_base}"
                    zf.write(fpath, arcname=arcname)
            return zip_path, playlist_title, True
        else:
            # Jeden soubor
            only_file = mp3_files[0]
            # Použijeme název z info pokud je dostupný a sanitizujeme
            title = info.get("title") or os.path.splitext(os.path.basename(only_file))[0]
            safe_name = safe_filename(title) + ".mp3"
            # Můžeme přejmenovat soubor v tmpdir na bezpečný název (volitelné)
            safe_path = os.path.join(tmpdir, safe_name)
            os.replace(only_file, safe_path)
            return safe_path, title, False
    except Exception:
        # při chybě smažeme tmpdir a znovu zvedneme výjimku
        shutil.rmtree(tmpdir, ignore_errors=True)
        raise

if url:
    if st.button("Připravit ke stažení"):
        try:
            with st.spinner("Zpracovávám audio... Momentík."):
                # Zkusíme stáhnout (případně celý playlist)
                result_path, display_name, is_zip = download_audio_to_tmp(url)
            st.success(f"Hotovo: {display_name}")

            # Velká poznámka: st.download_button načte soubor do paměti. U velmi velkých playlistů
            # může dojít k velké spotřebě paměti. Pokud to bude problém, je lepší řešení
            # servírovat soubory přes CDN nebo jednoduchý HTTP endpoint.
            with open(result_path, "rb") as f:
                data = f.read()

            if is_zip:
                out_filename = safe_filename(display_name) + ".zip"
                mime = "application/zip"
            else:
                out_filename = safe_filename(display_name) + ".mp3"
                mime = "audio/mpeg"

            st.download_button(
                label="Stáhnout",
                data=data,
                file_name=out
          
