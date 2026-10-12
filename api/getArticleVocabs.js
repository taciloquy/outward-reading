const cloudbase = require("@cloudbase/node-sdk");
const app = cloudbase.init({ env: cloudbase.SYMBOL_CURRENT_ENV });
const db = app.database();

exports.main = async (event) => {
  const { articleId } = event.queryStringParameters;
  if (!articleId) return { statusCode: 400, body: JSON.stringify([]) };

  const res = await db.sql(
    `SELECT id AS _id, article_id AS "articleId", word, phonetic, definition
     FROM vocab WHERE article_id = $1 ORDER BY id ASC`,
    [articleId]
  );

  const rows = res.data || res.records || res || [];
  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rows)
  };
};
