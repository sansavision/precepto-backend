CREATE MIGRATION m1ee7nw4ihljhklm7jjku7tsd3bqi5onkqbscenxgjv3ucooe5boaa
    ONTO m12yuwe2o2eafopqgxxkq3y4bhpuv74oij7xaplxqpqc5lbwitt23a
{
  CREATE TYPE default::AudioChunk {
      CREATE REQUIRED PROPERTY chunk_id: std::str;
      CREATE REQUIRED PROPERTY recording_id: std::str;
      CREATE CONSTRAINT std::exclusive ON ((.chunk_id, .recording_id));
      CREATE INDEX ON (.chunk_id);
      CREATE INDEX ON (.recording_id);
      CREATE REQUIRED PROPERTY created_at: std::datetime {
          SET default := (std::datetime_current());
      };
      CREATE REQUIRED PROPERTY data_path: std::str;
      CREATE REQUIRED PROPERTY end_time: std::float64;
      CREATE REQUIRED PROPERTY start_time: std::float64;
      CREATE REQUIRED PROPERTY status: std::str {
          CREATE CONSTRAINT std::one_of('active', 'deleted', 'replaced');
      };
  };
};
