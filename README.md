# mitkobalabanov.com

Статичен сайт: стена с всички видеа, страница за всяко видео с Vimeo плейър, About и Contact.
Няма зависимости – сайтът се сглобява от `build.py` (Python 3, само стандартната библиотека).

## Как се обновява

При всяка промяна в `main` GitHub сам сглобява и публикува сайта (`.github/workflows/deploy.yml`).
Достатъчно е да редактираш файл в GitHub и да натиснеш „Commit changes".

### Ново видео

Добави нов ред най-отгоре в `videos.json`:

```json
{"id": "123456789", "hash": "abcdef1234", "title": "Заглавие", "year": 2026, "thumb": "2159459542-6a47…", "width": 3840, "height": 2160, "credits": [["Director", "Име"]]}
```

- `id` и `hash` – от линка за вграждане на видеото във Vimeo: `player.vimeo.com/video/<id>?h=<hash>`.
- `thumb` – частта от адреса на кадъра във Vimeo между `/video/` и `-d`.
- `width` / `height` – размерът на видеото; определя пропорцията на плейъра.
- `credits` – двойки `["роля", "име"]`; ред без роля се пише като `["", "текст"]`.
- `loop` (по избор) – име на кратко видео без звук в `assets/loops/`, което се върти в плочката вместо кадъра.

Редът във файла е редът на началната страница.

### Текстове

Името, контактите, биото и филмографията са в `site.json`.

### Портрет

Сложи снимката като `assets/portrait.jpg`. Ако файлът липсва, About се показва без снимка.

### Loop-ове

Кратък MP4 без звук, широк около 640 px, до 5 секунди и под 500 KB:

```
ffmpeg -i input.mov -t 5 -vf "scale=640:-2,format=yuv420p" -c:v libx264 -crf 27 -movflags +faststart -an assets/loops/name.mp4
```

## Локален преглед

```
python3 build.py
python3 -m http.server --directory dist 8000
```
