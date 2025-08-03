-- All explanations for tries with one incorrect step
with cots_with_one_incorrect as (
    select * from cot_tries where(trie:: varchar like '%"incorrect"%') and(length(trie:: varchar) - length(replace(trie:: varchar, '"incorrect"', '')) = length('"incorrect"'))
) 
select jsonb_path_query(trie::jsonb, '$.**."explanation"') as explanation from cots_with_one_incorrect;