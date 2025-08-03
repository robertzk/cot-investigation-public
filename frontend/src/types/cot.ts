export interface TrieNode {
  content: string;
  children: TrieNode[];
  terminal: boolean;
  prefix: string;
}

export interface CotPath {
  id: number;
  cot_path: TrieNode[];
  is_unfaithful: boolean;
  answer_correct: boolean;
}

export interface TrieStructure {
  root: TrieNode;
  cot_paths: CotPath[];
}

export interface CotTrie {
  id: number;
  problem_id: number;
  model: string;
  dataset: string;
  question: string;
  answer: string;
  trie: TrieStructure;
  eval_: {
    is_correct: boolean;
    is_unfaithful: boolean;
  };
} 