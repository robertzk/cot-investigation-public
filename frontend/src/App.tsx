import React, { useState, useEffect } from 'react';
import { CotTrieGrid } from './components/CotTrieGrid';
import { TextField, Box, Paper, Select, MenuItem, FormControl, InputLabel, ToggleButtonGroup, ToggleButton, Modal, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, IconButton, Typography, SelectChangeEvent } from '@mui/material';
import "ag-grid-enterprise";
import { LicenseManager } from "ag-grid-enterprise";
import { useSearchParams } from 'react-router-dom';
import InfoIcon from '@mui/icons-material/Info';

import 'katex/dist/katex.min.css';

// LicenseManager.setLicenseKey("your License Key");
// Operate without a license for now: https://www.ag-grid.com/angular-data-grid/licensing/

import './App.css';

// Add interface for test cases
interface TestCase {
  model: string;
  problem_id: number;
  unfaithful: boolean;
  comments: string;
}

const App: React.FC = () => {
  const [searchParams] = useSearchParams();
  const experimentId = searchParams.get('experiment_id');
  const [problemId, setProblemId] = useState<string>('');
  const [selectedModel, setSelectedModel] = useState<string>('');
  const [selectedDataset, setSelectedDataset] = useState<string>('');
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [availableDatasets, setAvailableDatasets] = useState<string[]>([]);
  const [experimentDesc, setExperimentDesc] = useState<string>('');
  const [viewMode, setViewMode] = useState<'trie' | 'paths'>('trie');
  const [testCases, setTestCases] = useState<TestCase[]>([]);
  const [showTestCases, setShowTestCases] = useState(false);

  const handleProblemIdChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    // Only allow numbers and empty string
    const value = event.target.value.replace(/[^0-9]/g, '');
    setProblemId(value);
  };

  const handleModelChange = (event: SelectChangeEvent<string>) => {
    setSelectedModel(event.target.value);
  };

  const handleDatasetChange = (event: SelectChangeEvent<string>) => {
    setSelectedDataset(event.target.value);
  };

  // Callback to receive available models and datasets from CotTrieGrid
  const handleDataLoaded = (models: string[], datasets: string[]) => {
    setAvailableModels(models);
    setAvailableDatasets(datasets);
  };

  const handleViewModeChange = (
    _event: React.MouseEvent<HTMLElement>,
    newMode: 'trie' | 'paths'
  ) => {
    if (newMode !== null) {
      setViewMode(newMode);
    }
  };

  // Add function to fetch test cases
  const fetchTestCases = async () => {
    try {
      const response = await fetch('http://localhost:8001/api/test-cases', {
        credentials: 'include',
      });
      if (!response.ok) throw new Error('Failed to fetch test cases');
      const data = await response.json();
      setTestCases(data);
    } catch (error) {
      console.error('Error fetching test cases:', error);
    }
  };

  // Load test cases when modal is opened
  useEffect(() => {
    if (showTestCases) {
      fetchTestCases();
    }
  }, [showTestCases]);

  return (
    <div className="App" style={{ height: '100vh', width: '100%', display: 'flex', flexDirection: 'column' }}>
      <Box 
        component="header" 
        sx={{ 
          p: 2, 
          borderBottom: 1, 
          borderColor: 'divider',
          bgcolor: 'background.paper',
          display: 'flex',
          alignItems: 'center',
          gap: 2
        }}
      >
        <Typography variant="h6" component="h1" sx={{ m: 0, color: '#1a1a1a' }}>
          CoT Analysis
        </Typography>
        {experimentId && (
          <Typography variant="subtitle1" color="text.secondary" sx={{ m: 0 }}>
            Experiment {experimentId}{experimentDesc && `: ${experimentDesc}`}
          </Typography>
        )}
      </Box>

      <Box 
        component="main" 
        sx={{ 
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          p: 2,
          height: 0 // Required for flex child to scroll
        }}
      >
        <Paper 
          elevation={3} 
          sx={{ 
            p: 2, 
            mb: 2, 
            display: 'flex', 
            alignItems: 'center',
            gap: 2,
            backgroundColor: '#f5f5f5'
          }}
        >
          <TextField
            label="Filter by Problem ID"
            variant="outlined"
            size="small"
            value={problemId}
            onChange={handleProblemIdChange}
            sx={{ 
              width: '200px',
              backgroundColor: 'white',
              '& .MuiOutlinedInput-root': {
                borderRadius: '4px',
              }
            }}
            placeholder="Enter Problem ID"
          />

          <FormControl 
            size="small" 
            sx={{ 
              minWidth: 200,
              backgroundColor: 'white',
              borderRadius: '4px'
            }}
          >
            <InputLabel>Filter by Dataset</InputLabel>
            <Select
              value={selectedDataset}
              onChange={handleDatasetChange}
              label="Filter by Dataset"
            >
              <MenuItem value="">
                <em>All Datasets</em>
              </MenuItem>
              {availableDatasets.map((dataset) => (
                <MenuItem key={dataset} value={dataset}>
                  {dataset}
                </MenuItem>
              ))}
            </Select>
          </FormControl>

          <FormControl 
            size="small" 
            sx={{ 
              minWidth: 200,
              backgroundColor: 'white',
              borderRadius: '4px'
            }}
          >
            <InputLabel>Filter by Model</InputLabel>
            <Select
              value={selectedModel}
              onChange={handleModelChange}
              label="Filter by Model"
            >
              <MenuItem value="">
                <em>All Models</em>
              </MenuItem>
              {availableModels.map((model) => (
                <MenuItem key={model} value={model}>
                  {model}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          
          <ToggleButtonGroup
            value={viewMode}
            exclusive
            onChange={handleViewModeChange}
            size="small"
            sx={{ ml: 'auto' }}
          >
            <ToggleButton value="trie">
              Trie View
            </ToggleButton>
            <ToggleButton value="paths">
              Paths View
            </ToggleButton>
          </ToggleButtonGroup>

          <IconButton 
            onClick={() => setShowTestCases(true)}
            sx={{ ml: 2 }}
            title="View Test Cases"
          >
            <InfoIcon />
          </IconButton>
        </Paper>

        <Box sx={{ flex: 1, minHeight: 0, height: '100%' }}> {/* Container for grid */}
          <CotTrieGrid 
            problemIdFilter={problemId} 
            modelFilter={selectedModel}
            datasetFilter={selectedDataset}
            onDataLoaded={handleDataLoaded}
            experimentId={experimentId ? parseInt(experimentId) : undefined}
            onExperimentDesc={setExperimentDesc}
            viewMode={viewMode}
          />
        </Box>
      </Box>

      <Modal
        open={showTestCases}
        onClose={() => setShowTestCases(false)}
        aria-labelledby="test-cases-modal"
      >
        <Box sx={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          width: '90%',
          maxHeight: '90vh',
          bgcolor: 'background.paper',
          boxShadow: 24,
          p: 4,
          overflow: 'auto',
          borderRadius: 1,
        }}>
          <Typography variant="h6" component="h2" gutterBottom>
            Test Cases
          </Typography>
          <TableContainer>
            <Table stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Model</TableCell>
                  <TableCell>Problem ID</TableCell>
                  <TableCell>Unfaithful</TableCell>
                  <TableCell>Comments</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {testCases.map((testCase, index) => (
                  <TableRow 
                    key={index}
                    sx={{ 
                      backgroundColor: testCase.unfaithful ? '#F3E5F5' : 'inherit',
                      '&:hover': { backgroundColor: testCase.unfaithful ? '#E1BEE7' : '#f5f5f5' }
                    }}
                  >
                    <TableCell>{testCase.model}</TableCell>
                    <TableCell>{testCase.problem_id}</TableCell>
                    <TableCell>{testCase.unfaithful ? 'Yes' : 'No'}</TableCell>
                    <TableCell style={{ whiteSpace: 'pre-wrap' }}>{testCase.comments}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      </Modal>
    </div>
  );
};

export default App; 