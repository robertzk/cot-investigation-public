import React, { useState, useEffect } from 'react';
import { AgGridReact } from 'ag-grid-react';
import { ColDef, GridReadyEvent } from 'ag-grid-community';
import { Box, Typography, Paper, Tooltip, Collapse, Button, Divider, Chip } from '@mui/material';
import { CotTrie, TrieNode } from '../types/cot';

import { InlineMath } from 'react-katex';

import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

const renderLatexString = (text: string) => {
  // First split on LaTeX blocks that use \begin and \end
  const blockParts = text.split(/(\\\begin{.*?}.*?\\\end{.*?})/s);
  
  return blockParts.map((part, index) => {
    // If this part starts with \begin, treat it as LaTeX
    if (part.startsWith('\\begin')) {
      try {
        return <InlineMath key={index}>{part}</InlineMath>;
      } catch (error) {
        console.warn('Failed to render LaTeX block:', part, error);
        return <span key={index} style={{color: 'red'}}>{part}</span>;
      }
    }
    
    // For non-block parts, handle inline $ delimited math as before
    const inlineParts = part.split(/(\$[^\$]+\$)/g);
    return inlineParts.map((inlinePart, inlineIndex) => {
      if (inlinePart.startsWith('$') && inlinePart.endsWith('$')) {
        const latex = inlinePart.slice(1, -1);
        try {
          return <InlineMath key={`${index}-${inlineIndex}`}>{latex}</InlineMath>;
        } catch (error) {
          console.warn('Failed to render LaTeX:', latex, error);
          return <span key={`${index}-${inlineIndex}`} style={{color: 'red'}}>{inlinePart}</span>;
        }
      }
      return <span key={`${index}-${inlineIndex}`}>{inlinePart}</span>;
    });
  });
};


const TrieStepView: React.FC<{
  step: string;
  index: number;
  isIncorrect: boolean;
  stepIndex?: number;
  args?: any;
  secondaryEvalStatuses?: string[];
}> = ({ step, index, isIncorrect, stepIndex, args, secondaryEvalStatuses = [] }) => {
  const getPreBgColor = () => {
    if (secondaryEvalStatuses.includes('unfaithful')) {
      return '#2A0066';
    }
    if (secondaryEvalStatuses.includes('unused')) {
      return '#E0E0E0';
    }
    return isIncorrect ? '#662322' : 'grey.100';
  };

  const getPreTextColor = () => {
    if (secondaryEvalStatuses.includes('unfaithful')) {
      return '#ffffff';
    }
    return 'inherit';
  };

  return (
    <div>
      <div
        style={{
          border: '1px solid #e0e0e0',
          borderRadius: '4px',
          padding: '8px',
          marginBottom: '8px'
        }}
      >
        {renderLatexString(step)}
      </div>
      {(stepIndex !== undefined || args) && (
        <Box
          component="pre"
          sx={{
            mt: 1,
            p: 1,
            bgcolor: getPreBgColor(),
            color: getPreTextColor(),
            borderRadius: 1,
            fontSize: '0.75rem',
            overflow: 'auto',
            maxHeight: '200px'
          }}
        >
          {stepIndex !== undefined && `Continuation ${stepIndex}`}
          {args && ` | ${JSON.stringify(args)}`}
        </Box>
      )}
    </div>
  );
};

const TrieNodeView: React.FC<{ node: TrieNode, level?: number }> = ({ node, level = 0 }) => {
  const [expanded, setExpanded] = useState(false);
  const isIncorrect = node.content.correct === 'incorrect' || node.content.answer_correct?.correct === 'incorrect';
  
  // Get unique secondary evaluation statuses
  const secondaryEvalStatuses = node.content.secondary_eval?.evaluations
    ? Array.from(new Set(
        Object.values(node.content.secondary_eval.evaluations)
          .map((eval_) => ["trivial"].includes(eval_.severity) ? null : eval_.status)
          .filter(Boolean)
      ))
    : [];

  // Get severities of unfaithful evaluations
  const unfaithfulSeverities = node.content.secondary_eval?.evaluations
    ? Array.from(new Set(
        Object.entries(node.content.secondary_eval.evaluations)
          .filter(([_, eval_]) => eval_.status === 'unfaithful')
          .map(([_, eval_]) => eval_.severity)
      ))
    : [];

  // Determine background color based on secondary evaluations
  const getBgColor = () => {
    if (!node.content.secondary_eval) {
      return isIncorrect ? 'error.light' : 'background.paper';
    }

    if (secondaryEvalStatuses.includes('unfaithful')) {
      return '#4A148C';  // dark purple
    }
    if (secondaryEvalStatuses.includes('unused')) {
      return '#F5F5F5';  // light gray
    }
    if (secondaryEvalStatuses.every(status => status === 'incorrect')) {
      return isIncorrect ? 'error.light' : 'background.paper';
    }
    return isIncorrect ? 'error.light' : 'background.paper';
  };

  // Get text color based on background
  const getTextColor = () => {
    if (secondaryEvalStatuses.includes('unfaithful')) {
      return '#ffffff';  // white text for dark purple bg
    }
    if (secondaryEvalStatuses.includes('unused')) {
      return 'text.primary';  // normal text for light gray bg
    }
    return isIncorrect ? '#ffffff' : 'text.primary';
  };
  
  // Format secondary evaluations for tooltip
  const secondaryEvalTooltip = node.content.secondary_eval?.evaluations
    ? "\n\n***** Secondary evals:\n" + Object.entries(node.content.secondary_eval.evaluations)
        .map(([idx, eval_], i) => 
          `(${Number(idx) + 1}) ${eval_.status} = ${eval_.explanation}`
        )
        .join('\n')
    : '';
  
  const tooltipContent = [
    node.content.explanation,
    node.content.answer_correct?.explanation ? 
      ` ***** Answer Explanation: ${node.content.answer_correct.explanation}` : 
      null,
    secondaryEvalTooltip  // Add secondary evaluations to tooltip
  ].filter(Boolean).join('\n\n');
  
  // Create status text with secondary evaluations
  const secondaryEvalText = secondaryEvalStatuses.length > 0
    ? `2nd Eval: ${secondaryEvalStatuses.join(', ')} | `
    : '';

  const statusText = [
    secondaryEvalText,
    `Status: ${node.content.correct}`,
    node.content.answer_correct ? 
      ` | Final answer: ${node.content.answer_correct.correct}` : 
      null,
    node.terminal ? '(terminal)' : null
  ].filter(Boolean).join(' ');
  
  const secondEvalStatus = secondaryEvalStatuses.includes('unfaithful') ? 'unfaithful' : (
    secondaryEvalStatuses.includes('unused') ? 'unused' : (
      secondaryEvalStatuses.every(status => status === 'incorrect') ? 'incorrect' : 'none'
    )
  );

  // Get border color based on background
  const getBorderColor = () => {
    if (!node.content.secondary_eval) {
      return isIncorrect ? 'error.main' : 'grey.300';
    }

    if (secondaryEvalStatuses.includes('unfaithful')) {
      return '#2A0066';  // darker purple
    }
    if (secondaryEvalStatuses.includes('unused')) {
      return '#BDBDBD';  // darker gray
    }
    if (secondaryEvalStatuses.every(status => status === 'incorrect')) {
      return 'error.main';
    }
    return isIncorrect ? 'error.main' : 'grey.300';
  };

  return (
    <Box sx={{ maxWidth: '1400px', margin: '0 auto' }}>
    <Box sx={{ ml: level * 2, mb: 2, maxWidth: '1400px'}}>
      <Tooltip 
        title={tooltipContent || "No explanation available"} 
        placement="right"
        arrow
      >
        <Paper 
          sx={{ 
            p: 2, 
            bgcolor: getBgColor(),
            border: 1,
            borderColor: getBorderColor(),
            wordBreak: 'break-word',
            cursor: 'pointer',
            '&:hover': {
              boxShadow: 2,
            }
          }}
          onClick={() => setExpanded(!expanded)}
        >
          <Typography 
            variant="body1" 
            color={getTextColor()}
            fontWeight={isIncorrect ? 'bold' : 'normal'}
            sx={{ whiteSpace: 'pre-wrap' }}
          >
            {/* Always show first step */}
            <TrieStepView 
              step={node.content.steps[0]}
              index={0}
              isIncorrect={isIncorrect}
              stepIndex={node.content.step_indices?.[0]}
              args={node.content.args?.[0]}
              secondaryEvalStatuses={secondaryEvalStatuses}
            />
            
            {/* Show remaining steps when expanded */}
            <Collapse in={expanded}>
              {node.content.steps.slice(1).map((step: string, idx: number) => (
                <TrieStepView 
                  key={idx + 1}
                  step={step}
                  index={idx + 1}
                  isIncorrect={isIncorrect}
                  stepIndex={node.content.step_indices?.[idx + 1]}
                  args={node.content.args?.[idx + 1]}
                  secondaryEvalStatuses={secondaryEvalStatuses}
                />
              ))}
            </Collapse>
          </Typography>
          
          <Typography variant="caption" color={getTextColor()}>
            {statusText}
            {unfaithfulSeverities.length > 0 && (
               <span style={{ marginLeft: '8px', fontStyle: 'italic' }}> | Unfaithful:
                {unfaithfulSeverities.join(', ')}
              </span>
            )}
            {node.content.steps.length > 1 && (
              <span style={{ marginLeft: '8px', fontStyle: 'italic' }}>
                {expanded ? '(Click to collapse)' : `(Click to show ${node.content.steps.length - 1} more equivalent steps)`}
              </span>
            )}
          </Typography>
        </Paper>
      </Tooltip>
      
      {node.children.length > 0 && (
        <Box sx={{ mt: 1 }}>
          {node.children.map((child, idx) => (
            <TrieNodeView key={idx} node={child} level={level + 1} />
          ))}
        </Box>
      )}
    </Box>
    </Box>
  );
};

const DetailGridRenderer: React.FC<{ data: CotTrie, viewMode: 'trie' | 'paths' }> = ({ data, viewMode }) => {
  // Safely access paths with optional chaining and default to empty array
  const relevantPaths = data?.trie?.cot_paths?.filter(
    path => path.is_unfaithful && path.answer_correct
  ) || [];

  return (
    <Box 
      sx={{ 
        p: 2, 
        bgcolor: 'background.paper',
        height: '600px',
        overflow: 'auto',
        '& > *': {
          margin: '0 auto',
          maxWidth: '1200px'
        }
      }}
    >
      <Box sx={{ mb: 2 }}>
        <Typography variant="h6">
          Chain of Thought {viewMode === 'trie' ? 'Trie Structure' : 'Paths'}
        </Typography>
        <Typography variant="body1" sx={{ mt: 1 }}>
          Question: {renderLatexString(data.question)}
        </Typography>
        <Typography variant="body1" sx={{ mt: 1 }}>
          Answer: {renderLatexString(data.answer)}
        </Typography>
      </Box>

      {viewMode === 'trie' ? (
        data?.trie?.root && <TrieNodeView node={data.trie.root} />
      ) : (
        <Box>
          {relevantPaths.length === 0 ? (
            <Typography color="text.secondary" sx={{ mt: 2 }}>
              No unfaithful paths leading to correct answers found.
            </Typography>
          ) : (
            relevantPaths.map((path, index) => (
              <React.Fragment key={path.id || index}>
                {index > 0 && <Divider sx={{ my: 3 }} />}
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle1" color="primary" fontWeight="medium">
                    Path {path.id || index + 1}
                  </Typography>
                </Box>
                <Box sx={{ '& > *': { ml: '0 !important' } }}>
                  {path.cot_path?.map((node, nodeIndex) => (
                    <TrieNodeView 
                      key={nodeIndex}
                      node={{
                        content: node.content,
                        children: [],
                        terminal: nodeIndex === path.cot_path.length - 1,
                        prefix: ''
                      }}
                      level={0}
                    />
                  ))}
                </Box>
              </React.Fragment>
            ))
          )}
        </Box>
      )}
    </Box>
  );
};

const AnswerCellRenderer: React.FC<{ value: string }> = ({ value }) => {
  const truncateLength = 150;
  const shouldTruncate = value.length > truncateLength;
  const displayText = shouldTruncate 
    ? '...' + value.slice(-truncateLength)
    : value;

  return (
    <Tooltip 
      title={shouldTruncate ? value : ""}
      placement="top-start"
      arrow
    >
      <div style={{ 
        whiteSpace: 'pre-wrap',
        lineHeight: '1.5',
        fontFamily: 'inherit',
        cursor: shouldTruncate ? 'help' : 'default'
      }}>
        {displayText}
      </div>
    </Tooltip>
  );
};

// Move column definitions outside component
const columnDefs: ColDef[] = [
  { field: 'expand', cellRenderer: 'agGroupCellRenderer', width: 50 },
  { 
    field: 'problem_id', 
    headerName: 'Problem ID', 
    width: 120 
  },
  { 
    field: 'dataset', 
    headerName: 'Dataset', 
    width: 120 
  },
  { 
    field: 'question', 
    headerName: 'Question', 
    width: 400,
    flex: 1,
    wrapText: true,
    autoHeight: true,
    cellStyle: {
      'white-space': 'pre-wrap',
      'line-height': '1.5',
      'padding': '8px'
    },
    cellRenderer: (params: any) => {
      return <div style={{ 
        whiteSpace: 'pre-wrap',
        lineHeight: '1.5',
        fontFamily: 'inherit'
      }}>{renderLatexString(params.value)}</div>;
    }
  },
  { 
    field: 'answer', 
    headerName: 'Answer', 
    width: 400,
    flex: 1,
    wrapText: true,
    autoHeight: true,
    cellRenderer: (params: any) => {
      const truncateLength = 150;
      const shouldTruncate = params.value.length > truncateLength;
      const displayText = shouldTruncate 
        ? '...' + params.value.slice(-truncateLength)
        : params.value;

      return (
        <Tooltip 
          title={shouldTruncate ? renderLatexString(params.value) : ""}
          placement="top-start"
          arrow
        >
          <div style={{ 
            whiteSpace: 'pre-wrap',
            lineHeight: '1.5',
            fontFamily: 'inherit',
            cursor: shouldTruncate ? 'help' : 'default'
          }}>
            {renderLatexString(displayText)}
          </div>
        </Tooltip>
      );
    }
  },
  { 
    field: 'model', 
    headerName: 'Model', 
    width: 200 
  },
  { 
    field: 'incorrect_step_count', 
    headerName: 'Incorrect Steps', 
    width: 150,
    sort: 'desc'
  },
];

const defaultColDef: ColDef = {
  sortable: true,
  filter: true,
  resizable: true
};

interface CotTrieGridProps {
  problemIdFilter?: string;
  modelFilter?: string;
  datasetFilter?: string;
  onDataLoaded?: (models: string[], datasets: string[]) => void;
  experimentId?: number;
  onExperimentDesc?: (desc: string) => void;
  viewMode: 'trie' | 'paths';
}

const getRowStyle = (params: any) => {
  const trie = params.data;
  const hasUnfaithfulCorrectPath = trie.trie.cot_paths?.some(
    (path: any) => path.is_unfaithful && path.answer_correct
  );
  
  return hasUnfaithfulCorrectPath ? { backgroundColor: '#F3E5F5' } : {}; // Very light purple
};

export const CotTrieGrid: React.FC<CotTrieGridProps> = ({ 
  problemIdFilter, 
  modelFilter,
  datasetFilter,
  onDataLoaded,
  experimentId,
  onExperimentDesc,
  viewMode,
}) => {
  const [allData, setAllData] = useState<CotTrie[]>([]);  // Store all data
  const [rowData, setRowData] = useState<CotTrie[]>([]);  // Store filtered data
  const [loading, setLoading] = useState(true);
  const [uniqueModels, setUniqueModels] = useState<string[]>([]);
  const [uniqueDatasets, setUniqueDatasets] = useState<string[]>([]);
  // Fetch data only once on mount
  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await fetch(
          experimentId ? 
            `http://localhost:8001/api/cot-tries/experiment?experiment_id=${experimentId}` 
            : 'http://localhost:8001/api/cot-tries/incorrect', 
          {
            credentials: 'include',
            headers: {
              'Content-Type': 'application/json',
            },
          }
        );
        
        if (!response.ok) throw new Error('Failed to fetch data');
        const data = await response.json();
        
        // Handle different response structures for experiment vs incorrect tries
        if (experimentId) {
          setAllData(data.tries || []);
          if (onExperimentDesc && data.experiment?.experiment_desc) {
            onExperimentDesc(data.experiment.experiment_desc);
          }
        } else {
          setAllData(data || []);
        }
        
        // Update unique models from the correct data source
        const tries = experimentId ? (data.tries || []) : (data || []);
        const newUniqueModels = Array.from(
          new Set(tries.map((trie: CotTrie) => trie.model))
        ).sort();
        const newUniqueDatasets = Array.from(
          new Set(tries.map((trie: CotTrie) => trie.dataset))
        ).sort();
        setUniqueModels(newUniqueModels);
        setUniqueDatasets(newUniqueDatasets);
        
        if (onDataLoaded) {
          onDataLoaded(newUniqueModels, newUniqueDatasets);
        }
      } catch (error) {
        console.error('Error fetching data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, [experimentId]); // Add dependencies

  // Filter data locally when filters change
  useEffect(() => {
    const filteredData = allData.filter((trie: CotTrie) => {
      const matchesProblemId = !problemIdFilter || 
        trie.problem_id.toString() === problemIdFilter;
      const matchesModel = !modelFilter || 
        trie.model === modelFilter;
      const matchesDataset = !datasetFilter || 
        trie.dataset === datasetFilter;
      return matchesProblemId && matchesModel && matchesDataset;
    });
    
    setRowData(filteredData);
  }, [allData, problemIdFilter, modelFilter, datasetFilter]);

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="ag-theme-alpine" style={{ height: '80vh', width: '100%' }}>
      <AgGridReact
        rowData={rowData}
        columnDefs={columnDefs}
        defaultColDef={defaultColDef}
        masterDetail={true}
        detailRowHeight={650}
        detailCellRenderer={(props) => <DetailGridRenderer {...props} viewMode={viewMode} />}
        pagination={true}
        paginationPageSize={10}
        domLayout='autoHeight'
        getRowStyle={getRowStyle}
      />
    </div>
  );
}; 