module default {

  abstract type BaseObject {
    required  created_at : datetime {
      default := datetime_current();
    }
    required  updated_at : datetime {
      default := datetime_current();
    }
  }


  type User extending BaseObject {
    required  user_name : str{
      constraint exclusive;
    }
    first_name : str;
    last_name : str;
    email : str; 
    image_url : str;
    login_pass : str;
    is_admin : bool {
      default := false;
    }
    last_login : datetime;
    logged_in : bool {
      default := false;
    }
    required  category : str {
      default := "others";
    }
    multi Template := .<created_by[is Template];
    multi Transcription := .<created_by[is Template];

  }

  type Template extending BaseObject {
    required  name : str;
    description : str;
    template : str;
    is_public : bool {
      default := false;
    }
    image_url : str;
    required created_by : User {
      # constraint exclusive;
      on target delete delete source
    }
    multi shared_with : User;
  }

type Analytics extending BaseObject {
  required  backend_step : str;
  required  duration : float32;
  is_success : bool;
}
type Translation extending BaseObject {
  required  language : str;
  required  translation : str;
}

scalar type TranscriptionStatusType extending enum< 
  signed, not_signed, queued, failed, processing, draft
  >;


scalar type TranscriptionBackendStatusType extending enum< 
  draft ,recording_service, transcription_service, summarization_service, completed, failed
  >;

type Transcription extending BaseObject {
  required name : str;
  required status : TranscriptionStatusType {
    default := "draft";
  }
  required backend_status : TranscriptionBackendStatusType {
    default := "draft";
  }
  place_in_queue : int16;
  next_backend_step : str;
  multi analytics : Analytics;
  required  template : Template;
  required  created_by : User {
      # constraint exclusive;
      on target delete delete source
    }
  audio_url : str;
  transcript : str;
  final_transcript : str;
  backend_updated_at : datetime;
  duration : float32;
words : int16;
speakers : int16;
confidence : float32;
language : str;
speaker_labels : bool;
keywords : array<str>;
topics : array<str>;
actions : array<str>;
multi translations : Translation;
summary : str;
notes : str;
marked_for_delete : bool;
marked_for_delete_date : datetime;
}

type AuthToken extending BaseObject {
  required  token : str;
  required  user : User;
  required  expires_at : datetime;
 }

type AudioChunk {
  required property chunk_id -> str;
  required property recording_id -> str;
  required property start_time -> float64;
  required property end_time -> float64;
  required property status -> str {
      constraint one_of('active', 'deleted', 'replaced');
  }
  required property data_path -> str;
  required property created_at -> datetime {
      default := datetime_current();
  }
  index on (.recording_id);
  index on (.chunk_id);
  constraint exclusive on ((.chunk_id, .recording_id));
}
 
}
