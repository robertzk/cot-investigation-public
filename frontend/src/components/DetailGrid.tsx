import React from 'react';
import { Box, Typography, Paper } from '@mui/material';

interface Evaluation {
  id: number;
  correct: string;
  model: string;
  explanation: string;
}

interface Step {
  id: number;
  step_number: number;
  step_text: string;
  evaluations: Evaluation[];
}

interface DetailGridProps {
  steps: Step[];
}

export const DetailGrid: React.FC<DetailGridProps> = ({ steps }) => {
  return (
    <Box sx={{ p: 2 }}>
      {steps.map((step) => (
        <Paper key={step.id} sx={{ p: 2, mb: 2 }}>
          <Typography variant="h6" gutterBottom>
            Step {step.step_number}
          </Typography>
          <Typography paragraph>{step.step_text}</Typography>
          
          {step.evaluations.length > 0 && (
            <Box sx={{ ml: 2 }}>
              <Typography variant="subtitle1" gutterBottom>
                Evaluations:
              </Typography>
              {step.evaluations.map((evaluation) => (
                <Paper key={evaluation.id} sx={{ p: 2, mb: 1, bgcolor: 'grey.100' }}>
                  <Typography color={evaluation.correct === 'yes' ? 'success.main' : evaluation.correct === 'no' ? 'error.main' : 'text.primary'}>
                    {evaluation.correct.toUpperCase()} - Evaluated by {evaluation.model}
                  </Typography>
                  <Typography variant="body2" sx={{ mt: 1 }}>
                    {evaluation.explanation}
                  </Typography>
                </Paper>
              ))}
            </Box>
          )}
        </Paper>
      ))}
    </Box>
  );
}; 