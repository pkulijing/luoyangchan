-- release_id 用作前端路由标识符，必须唯一
DROP INDEX IF EXISTS idx_heritage_sites_release_id;
ALTER TABLE heritage_sites ADD CONSTRAINT heritage_sites_release_id_unique UNIQUE (release_id);
