CREATE MIGRATION m1doln6ydpb62l5kyizkdxmk7o63nedpkgkngma5teoqdngblw6qja
    ONTO initial
{
  CREATE ABSTRACT TYPE default::BaseObject {
      CREATE REQUIRED PROPERTY created_at: std::datetime {
          SET default := (std::datetime_current());
      };
      CREATE REQUIRED PROPERTY updated_at: std::datetime {
          SET default := (std::datetime_current());
      };
  };
  CREATE TYPE default::Analytics EXTENDING default::BaseObject {
      CREATE REQUIRED PROPERTY backend_step: std::str;
      CREATE REQUIRED PROPERTY duration: std::float32;
      CREATE PROPERTY is_success: std::bool;
  };
  CREATE TYPE default::Translation EXTENDING default::BaseObject {
      CREATE REQUIRED PROPERTY language: std::str;
      CREATE REQUIRED PROPERTY translation: std::str;
  };
  CREATE TYPE default::Transcription EXTENDING default::BaseObject {
      CREATE MULTI LINK analytics: default::Analytics;
      CREATE MULTI LINK translations: default::Translation;
      CREATE PROPERTY actions: array<std::str>;
      CREATE PROPERTY audio_url: std::str;
      CREATE REQUIRED PROPERTY backend_status: std::str;
      CREATE PROPERTY backend_updated_at: std::datetime;
      CREATE PROPERTY confidence: std::float32;
      CREATE PROPERTY duration: std::float32;
      CREATE PROPERTY final_transcript: std::str;
      CREATE PROPERTY keywords: array<std::str>;
      CREATE PROPERTY language: std::str;
      CREATE PROPERTY marked_for_delete: std::bool;
      CREATE PROPERTY marked_for_delete_date: std::datetime;
      CREATE REQUIRED PROPERTY name: std::str;
      CREATE PROPERTY next_backend_step: std::str;
      CREATE PROPERTY notes: std::str;
      CREATE PROPERTY place_in_queue: std::int16;
      CREATE PROPERTY speaker_labels: std::bool;
      CREATE PROPERTY speakers: std::int16;
      CREATE REQUIRED PROPERTY status: std::str;
      CREATE PROPERTY summary: std::str;
      CREATE PROPERTY topics: array<std::str>;
      CREATE PROPERTY transcript: std::str;
      CREATE PROPERTY words: std::int16;
  };
  CREATE TYPE default::Template EXTENDING default::BaseObject {
      CREATE PROPERTY description: std::str;
      CREATE PROPERTY image_url: std::str;
      CREATE PROPERTY is_public: std::bool {
          SET default := false;
      };
      CREATE REQUIRED PROPERTY name: std::str;
      CREATE PROPERTY template: std::str;
  };
  CREATE TYPE default::User EXTENDING default::BaseObject {
      CREATE REQUIRED PROPERTY category: std::str {
          SET default := 'others';
      };
      CREATE PROPERTY email: std::str;
      CREATE PROPERTY first_name: std::str;
      CREATE PROPERTY image_url: std::str;
      CREATE PROPERTY is_admin: std::bool {
          SET default := false;
      };
      CREATE PROPERTY last_login: std::datetime;
      CREATE PROPERTY last_name: std::str;
      CREATE PROPERTY logged_in: std::bool {
          SET default := false;
      };
      CREATE PROPERTY login_pass: std::str;
      CREATE REQUIRED PROPERTY user_name: std::str {
          CREATE CONSTRAINT std::exclusive;
      };
  };
  ALTER TYPE default::Template {
      CREATE REQUIRED LINK created_by: default::User {
          ON TARGET DELETE DELETE SOURCE;
      };
      CREATE MULTI LINK shared_with: default::User;
  };
  ALTER TYPE default::User {
      CREATE MULTI LINK Template := (.<created_by[IS default::Template]);
      CREATE MULTI LINK Transcription := (.<created_by[IS default::Template]);
  };
  ALTER TYPE default::Transcription {
      CREATE REQUIRED LINK template: default::Template;
      CREATE REQUIRED LINK created_by: default::User {
          ON TARGET DELETE DELETE SOURCE;
      };
  };
};
