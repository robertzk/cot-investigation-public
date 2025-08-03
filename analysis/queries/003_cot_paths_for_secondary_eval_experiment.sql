select id, cot_trie_id, cot_trie_eval_experiment_record_id, answer_correct, is_unfaithful,
node_ids, substr(cot_path::varchar, 1, 100) as cot_path
from cot_path limit 3;

select id, cot_trie_id, cot_trie_eval_experiment_record_id, answer_correct, is_unfaithful,
node_ids, cot_path
from cot_path limit 3;

select * from cot_trie_eval_experiment_record where id = 1059;


select id, cot_trie_id, answer_correct, is_unfaithful from cot_path limit 5;

select * from cot_trie_eval_experiment_record where experiment_id = 15 limit 5;

-- delete from cot_path
-- where cot_trie_eval_experiment_record_id in (
--     select id from cot_trie_eval_experiment_record 
--     where experiment_id = 15
-- );
-- delete from cot_trie_eval_experiment_record where experiment_id = 15;

-- INSERT INTO cot_trie_eval_experiment_record (experiment_id, problem_id, trie_evaled, cot_trie_id, model)
-- SELECT 15, problem_id, trie_evaled_alt1, id, model
-- FROM cot_tries
-- WHERE problem_id IN (
--  104, 143, 324, 425, 436, 474, 516, 841, 996, 1203, 1228, 1541, 1555, 1677, 1766, 1856, 1913, 2024, 2076, 2177, 2407, 2503, 2654, 2731, 2835, 2966, 3164, 3200, 3296, 3323, 4118, 4168, 4203, 4240, 4241, 4418, 4613, 5159, 5225, 5419, 5544, 5841,
--  33, 34, 39, 141, 160, 242, 318, 373, 391, 466, 503, 516, 538, 554, 573, 616, 617, 632, 646, 666, 668, 697, 747, 791, 846, 1038, 1051, 1118, 1124, 1149, 1262, 1384, 1389, 1411, 1438, 2722, 2727, 4187, 5516, 5535
-- ) AND trie_evaled_alt1 is not null;

select id, description from cot_trie_eval_experiment;








