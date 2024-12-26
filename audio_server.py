from flask import Flask, send_from_directory, abort
import os

app = Flask(__name__)

@app.route('/audio/<recording_id>')
def get_audio(recording_id):
    audio_dir = 'audio_chunks'
    audio_filename = f"{recording_id}_combined.webm"
    if os.path.exists(os.path.join(audio_dir, audio_filename)):
        return send_from_directory(audio_dir, audio_filename)
    else:
        return abort(404, description="Audio not found")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
