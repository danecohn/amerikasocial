export function createBoosts(db,{now=Date.now}={}){
 db.exec(`CREATE TABLE IF NOT EXISTS boost_usage(id INTEGER PRIMARY KEY,operator TEXT NOT NULL,actor TEXT NOT NULL,kind TEXT NOT NULL,created INTEGER NOT NULL);
 CREATE INDEX IF NOT EXISTS boost_usage_window ON boost_usage(operator,kind,created);
 CREATE INDEX IF NOT EXISTS likes_post ON likes(post);
 CREATE INDEX IF NOT EXISTS reposts_post ON reposts(post);`);
 const ownerSql="CASE WHEN a.kind='human' THEN a.id ELSE a.operator_id END";
 function operator(id){const a=db.prepare('SELECT id,kind,operator_id FROM actors WHERE id=?').get(id);return a?.kind==='human'?a.id:a?.operator_id||id;}
 function reserve(id,kind){const group=operator(id),limit=kind==='like'?120:60;const count=db.prepare('SELECT COUNT(*) AS n FROM boost_usage WHERE operator=? AND kind=? AND created>?').get(group,kind,now()-3600000).n;
  if(count>=limit)throw Object.assign(Error(`Your account and linked bots share a limit of ${limit} ${kind==='like'?'likes':'reposts'} per hour. Try again later.`),{status:429});
  db.prepare('INSERT INTO boost_usage(operator,actor,kind,created) VALUES (?,?,?,?)').run(group,id,kind,now());
  db.prepare('DELETE FROM boost_usage WHERE created<?').run(now()-86400000);
 }
 function stats(post){const author=operator(post.author);function reaction(table){return db.prepare(`SELECT COUNT(*) AS accounts,COALESCE(SUM(a.kind='human'),0) AS humans,COALESCE(SUM(a.kind='agent'),0) AS agents,COUNT(DISTINCT CASE WHEN owner.id IS NOT NULL AND owner.suspended_at IS NULL THEN ${ownerSql} END) AS operators,COUNT(DISTINCT CASE WHEN owner.id IS NOT NULL AND owner.suspended_at IS NULL AND ${ownerSql}!=? THEN ${ownerSql} END) AS independentOperators FROM ${table} r JOIN actors a ON a.id=r.actor LEFT JOIN actors owner ON owner.id=${ownerSql} AND owner.kind='human' WHERE r.post=? AND a.suspended_at IS NULL`).get(author,post.uri);}
  const likes=reaction('likes'),reposts=reaction('reposts');const influence=db.prepare(`SELECT COUNT(DISTINCT ${ownerSql}) AS n FROM (SELECT actor FROM likes WHERE post=? UNION SELECT actor FROM reposts WHERE post=?) r JOIN actors a ON a.id=r.actor JOIN actors owner ON owner.id=${ownerSql} AND owner.kind='human' WHERE a.suspended_at IS NULL AND owner.suspended_at IS NULL AND ${ownerSql}!=?`).get(post.uri,post.uri,author).n;
  return {likes,reposts,independentSupporters:influence};
 }
 function firstReaction(id,post,kind){const table=kind==='like'?'likes':'reposts';return !db.prepare(`SELECT 1 FROM ${table} r JOIN actors a ON a.id=r.actor WHERE r.post=? AND COALESCE(${ownerSql},a.id)=? LIMIT 1`).get(post,operator(id));}
 return {operator,reserve,stats,firstReaction};
}
