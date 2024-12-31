CREATE MIGRATION m12yuwe2o2eafopqgxxkq3y4bhpuv74oij7xaplxqpqc5lbwitt23a
    ONTO m13pglcb32oyoz7btomouu7jax6mxnzwotxx3yjjsyaj5k7gzuudtq
{
  CREATE TYPE default::AuthToken EXTENDING default::BaseObject {
      CREATE REQUIRED LINK user: default::User;
      CREATE REQUIRED PROPERTY expires_at: std::datetime;
      CREATE REQUIRED PROPERTY token: std::str;
  };
};
