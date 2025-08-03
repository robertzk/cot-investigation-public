export interface GSM8KResponse {
  id: number;
  question: string;
  model_name: string;
  raw_response: string;
  params: {
    temperature: number;
    [key: string]: any;
  };
} 