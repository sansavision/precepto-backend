# Create a new transcription
INSERT Transcription {
    name := <str>$name,
    status := <TranscriptionStatusType>$status,
    backend_status := <TranscriptionBackendStatusType>$backend_status,
    place_in_queue := <optional int16>$place_in_queue,
    next_backend_step := <optional str>$next_backend_step,
    analytics := { (insert Analytics { 
                            backend_step:= <str>$backend_step,
                            duration:= <float32>$backend_step_duration,
                            is_success:= <bool>$backend_step_is_success
                        })},
    template :=   (select Template filter .id = <uuid>$template_id),
    created_by :=  (select User filter .id = <uuid>$user_id),
    audio_url := <optional str>$audio_url,
    transcript := <optional str>$transcript,
    final_transcript := <optional str>$final_transcript,
    backend_updated_at := <optional datetime>$backend_updated_at,
    duration := <optional float32>$duration,
    words := <optional int16>$words,
    speakers := <optional int16>$speakers,
    confidence := <optional float32>$confidence,
    language := <optional str>$language,
    speaker_labels := <optional bool>$speaker_labels,
    # keywords := ['keyword1', 'keyword2'],   # TODO: V1.1 make keyqword, topics, actions, translations as array
    # topics := ['topic1', 'topic2'],       
    # actions := ['action1', 'action2'],   
    translations := {(insert Translation { 
                                language := <str>$translation_language,
                                translation := <str>$translation
                        })},  # Add all related Translation IDs
    summary := <optional str>$summary,
    notes := <optional str>$notes,
    marked_for_delete := <optional bool>$marked_for_delete,
    marked_for_delete_date := <optional datetime>$marked_for_delete_date
};