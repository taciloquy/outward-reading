const cloudbase = require("@cloudbase/node-sdk");
const app = cloudbase.init({ env: cloudbase.SYMBOL_CURRENT_ENV });
const db = app.database();

exports.main = async (event) => {
  const { date } = event.queryStringParameters;
  if (!date) return { statusCode: 400, body: JSON.stringify([]) };

  const res = await db.sql(
    `SELECT id AS _id, title, publish_date AS "publishDate", file_key AS "fileKey",
            source, clean_path AS "cleanPath", annotated_path AS "annotatedPath"
     FROM articles WHERE publish_date = $1 ORDER BY id DESC`,
    [date]
  );

  const rows = res.data || res.records || res || [];
  return {
    statusCode: 200,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rows)
  };
};
