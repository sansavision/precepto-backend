CREATE MIGRATION m13pglcb32oyoz7btomouu7jax6mxnzwotxx3yjjsyaj5k7gzuudtq
    ONTO m1doln6ydpb62l5kyizkdxmk7o63nedpkgkngma5teoqdngblw6qja
{
  CREATE SCALAR TYPE default::TranscriptionBackendStatusType EXTENDING enum<draft, recording_service, transcription_service, summarization_service, completed, failed>;
  ALTER TYPE default::Transcription {
      ALTER PROPERTY backend_status {
          SET default := 'draft';
          SET TYPE default::TranscriptionBackendStatusType;
      };
  };
  CREATE SCALAR TYPE default::TranscriptionStatusType EXTENDING enum<signed, not_signed, queued, failed, processing, draft>;
  ALTER TYPE default::Transcription {
      ALTER PROPERTY status {
          SET default := 'draft';
          SET TYPE default::TranscriptionStatusType;
      };
  };
};
