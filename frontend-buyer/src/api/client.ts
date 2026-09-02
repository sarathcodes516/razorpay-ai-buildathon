import axios from 'axios';

const API = axios.create({ baseURL: 'http://localhost:8001/api' });

// Generic axios client for non-streaming calls (mandate creation etc.)
export default API;

// Keep this export so any other file that imports it doesn't break
export const startNegotiation = async (_mandate_id: string, _goal: string) => {
  throw new Error('Use AgentGateway streaming fetch instead of startNegotiation');
};
