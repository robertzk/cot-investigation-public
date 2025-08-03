from itertools import product
import random
class Foo:
    def _replace_cot_instruction(self, prompt: str, cot_instruction_seed: int) -> str:
        """
        Replace the cot instruction in an effort to generate some entropy in the model's
        response while keeping the deterministic reproducibility of the example with temperature 0.
        """
        if self.cot_instruction is None:
            raise ValueError("No cot instruction set. Use the set_cot_instruction method to set a cot instruction.")
        
        variations1 = {
            "Reason through your answer step by step, and number every step ",
            "Write down your answer by reasoning through it step by step. Number every step ",
            "Produce your answer by reasoning through it step by step. Number all steps ",
            "Construct an answer step by step, and enumerate all steps ",
            "Build your answer one step at a time, and number each of your steps ",
        }

        variations2 = {
            '("1.", "2.", etc.)',
            '("Step 1.", "Step 2.", etc.)',
            '("1: ", "2: ", etc.)"',
            '("Step 1: ", "Step 2: ", etc.)',
        }

        all_variations = list(product(variations1, variations2))
        random.seed(cot_instruction_seed)
        chosen_variation = random.choice(all_variations)
        chosen_variation = chosen_variation[0] + chosen_variation[1] + '.'
        
        return prompt.replace(self.cot_instruction, chosen_variation)

foo = Foo()
foo.cot_instruction = "Write down your answer step by step, and number each step."
print(foo._replace_cot_instruction("Write down your answer step by step, and number each step. Do some stuff", 1))
