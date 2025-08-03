import React, { useState, useEffect } from 'react';
import { AgGridReact } from 'ag-grid-react';
import axios from 'axios';
import { ColDef, GridOptions } from 'ag-grid-community';
import { DetailGrid } from './DetailGrid';

// Import AG Grid styles
import 'ag-grid-community/styles/ag-grid.css';
import 'ag-grid-community/styles/ag-theme-alpine.css';

interface GSM8KResponse {
  id: number;
  question: string;
  model_name: string;
  raw_response: string;
  params: Record<string, any>;
  steps: {
    id: number;
    step_number: number;
    step_text: string;
    evaluations: {
      id: number;
      correct: string;
      model: string;
      explanation: string;
    }[];
  }[];
}

const GSM8KGrid: React.FC = () => {
    const [rowData, setRowData] = useState<GSM8KResponse[]>([]);
    const [loading, setLoading] = useState<boolean>(true);

    // Configure the detail grid
    const detailGridOptions: GridOptions = {
        columnDefs: [
            { field: 'step_number', headerName: 'Step', width: 100 },
            { field: 'step_text', headerName: 'Description', flex: 2 },
            { 
                field: 'evaluation_count', 
                headerName: 'Evaluations',
                width: 120,
                valueGetter: (params) => params.data.evaluations?.length || 0
            },
            {
                field: 'correct_count',
                headerName: 'Correct',
                width: 120,
                valueGetter: (params) => 
                    params.data.evaluations?.filter(e => e.correct === 'yes').length || 0
            }
        ],
        defaultColDef: {
            sortable: true,
            filter: true,
        }
    };

    const columnDefs: ColDef[] = [
        { field: 'expand', cellRenderer: 'agGroupCellRenderer' },
        { field: 'id', headerName: 'ID', width: 100, sort: 'asc' },
        { field: 'question', headerName: 'Question', flex: 2 },
        { field: 'model_name', headerName: 'Model', width: 200 },
        { 
            field: 'step_count', 
            headerName: 'Steps',
            width: 100,
            valueGetter: (params) => params.data.steps?.length || 0
        },
        { 
            field: 'raw_response', 
            headerName: 'Response', 
            flex: 3,
            autoHeight: true,
            wrapText: true,
            cellStyle: { 
                'white-space': 'pre-wrap',
                'font-family': 'monospace',
                'background-color': '#f5f5f5',
                'padding': '8px'
            },
            cellRenderer: (params) => {
                return <pre style={{ 
                    margin: 0,
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    lineHeight: '1.0',
                }}>{params.value}</pre>;
            }
        }
    ];

    const defaultColDef: ColDef = {
        sortable: true,
        filter: true,
        resizable: true,
    };

    // Detail cell renderer params
    const detailCellRendererParams = {
        detailGridOptions: detailGridOptions,
        getDetailRowData: (params) => {
            params.successCallback(params.data.steps);
        },
        template: `
            <div> DETAILED GRID </div> `
            // <div style="padding: 20px;">
            //     <div style="font-weight: bold; margin-bottom: 10px;">Steps and Evaluations</div>
            //     <div data-ref="eDetailGrid"></div>
            // </div>
        // `
    };

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await axios.get<GSM8KResponse[]>('http://localhost:8001/api/gsm8k/responses');
                setRowData(response.data);
            } catch (error) {
                console.error('Error fetching data:', error);
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, []);

    if (loading) {
        return <div>Loading...</div>;
    }

    return (
        <div className="ag-theme-alpine" style={{ height: '80vh', width: '100%' }}>
            <AgGridReact
                rowData={rowData}
                columnDefs={columnDefs} defaultColDef={defaultColDef}
                masterDetail={true}
                detailCellRendererParams={detailCellRendererParams}
                detailRowHeight={400}
                pagination={true}
                paginationPageSize={20}
                domLayout='autoHeight'
            />
        </div>
    );
};

export default GSM8KGrid;