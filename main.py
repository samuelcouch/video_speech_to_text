import sys
import os
import json
from os.path import dirname, join, basename, splitext, abspath
from multiprocessing import Process

from moviepy.editor import AudioFileClip
from math import ceil

from watson_developer_cloud import SpeechToTextV1 as SpeechToText

def get_and_save_transcript(audio_file, transcript_file):
    with open(audio_file, 'rb') as af:
        resp = stt.recognize(af,
            content_type='audio/wav',
            timestamps=True,
            continuous=True,
            word_confidence=True,
            profanity_filter=False,
            word_alternatives_threshold=0.4)
        with open(transcript_file, 'w') as tf:
            tf.write(json.dumps(resp))


if __name__ == '__main__':
    # Get the mp4 from the input, create a project directory to work in
    filepath = sys.argv[1].strip()
    video_name = splitext(basename(filepath))[0]

    project_dir = join(dirname(__file__), 'media_data', 'projects', video_name)

    os.makedirs(project_dir, exist_ok=True)

    # Split large file into smaller chunks
    # (Watson speech to text has a 100MB filesize limit)

    audio = AudioFileClip(filepath)
    total_seconds = audio.duration

    sec_marker = 0
    CHUNK_LENGTH = 300

    segment_files = []

    while sec_marker < total_seconds:
        if not os.path.exists(join(project_dir, 'split_audio')):
            os.makedirs(join(project_dir, 'split_audio'))

        end_sec_marker = sec_marker + CHUNK_LENGTH

        if end_sec_marker > total_seconds:
            end_sec_marker = ceil(total_seconds)
            segment = audio.subclip(sec_marker)
        else:
            segment = audio.subclip(sec_marker, end_sec_marker)

        segment_base = '{}_{}.wav'.format(
            str(sec_marker),
            str(end_sec_marker))

        segment_full_path = join(project_dir, 'split_audio', segment_base)
        segment_files.append(segment_full_path)

        segment.write_audiofile(segment_full_path, verbose=False, progress_bar=False)
        sec_marker = end_sec_marker

    stt = SpeechToText(
          username=os.environ.get("STT_USERNAME"),
          password=os.environ.get("STT_PASSWORD"))

    if not os.path.exists(join(project_dir, 'split_transcripts')):
        os.makedirs(join(project_dir, 'split_transcripts'))

    trancription_jobs = []
    transcript_files = []

    for chunk in segment_files:
        transcript_file = '{}.json'.format(splitext(basename(chunk))[0])
        full_transcript_file = join(project_dir, 'split_transcripts', transcript_file)
        transcript_files.append(full_transcript_file)
        job = Process(target=get_and_save_transcript,
                      args=(chunk,full_transcript_file))
        job.start()

        trancription_jobs.append(job)

    for job in trancription_jobs:
        job.join()

    compiled_results = []
    compiled_dict = {'results': compiled_results, 'result_index': 0}

    for transcript_file in transcript_files:
        start_timestamp = int(basename(transcript_file).split('_')[0])
        with open(transcript_file) as tf:
            data = json.load(tf)
            transcription = ''
            for result in data['results']:
                for x in result.get('word_alternatives'):
                    x['start_time'] += start_timestamp
                    x['end_time'] += start_timestamp
                for alt in result.get('alternatives'):
                    transcription = alt['transcript'].rstrip()
                    for ts in alt['timestamps']:
                        ts[1] += start_timestamp
                        ts[2] += start_timestamp
                compiled_results.append(result)
                with open(join(project_dir, 'transcript.txt'), 'a+') as f:
                    f.write('{} '.format(transcription))
