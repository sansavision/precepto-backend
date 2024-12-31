# Update a transcription's information
UPDATE Transcription
FILTER .id = <uuid>$id
SET {
    name := <optional str>$name,
    status := <TranscriptionStatusType>$status,
    backend_status := <TranscriptionBackendStatusType>$backend_status,
    place_in_queue := <optional int16>$place_in_queue,
    next_backend_step := <str>$next_backend_step,
    # analytics := { <uuid>$analytics_id1, <uuid>$analytics_id2 }, ITS EASIER to just update the analytics directly
    template := (select Template filter .id = <uuid>$template_id) if exists <optional uuid>$template_id else .template,
    # created_by :=  (select User filter .id = <uuid>$user_id) if exists <optional uuid>$user_id else .created_by,
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
    # keywords := array<str>$keywords,
    # topics := array<str>$topics,
    # actions :=  array<str>$actions,
    # translations := { <uuid>$translation_id1, <uuid>$translation_id2 },
    summary := <optional str>$summary,
    notes := <optional str>$notes,
    marked_for_delete := <optional bool>$marked_for_delete,
    marked_for_delete_date := <optional datetime>$marked_for_delete_date
};

 