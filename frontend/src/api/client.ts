import axios from 'axios';
import { ChatResponse } from '../types/api';

const API = axios.create({ baseURL: 'http://localhost:8001/api' });

export const fetchCatalog = async () => (await API.get('/catalog')).data;

export const sendChatMessage = async (mandate_id: string, user_message: string): Promise<ChatResponse> => {
  return (await API.post('/storefront/chat', { mandate_id, user_message })).data;
};

export const recoverPayment = async (error_reason: string) => {
  return (await API.post('/storefront/recover', { error_reason })).data;
};
