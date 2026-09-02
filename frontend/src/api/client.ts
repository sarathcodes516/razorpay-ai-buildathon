import axios from 'axios';
import { ChatResponse } from '../types/api';

const API = axios.create({ baseURL: 'http://localhost:8001/api' });

export const fetchCatalog = async () => (await API.get('/catalog')).data;

export const sendChatMessage = async (
  user_message: string,
  history = '',
  current_cart: { sku: string; qty: number }[] = [],
): Promise<ChatResponse> => {
  return (await API.post('/storefront/chat', { user_message, history, current_cart })).data;
};

export const recoverPayment = async (error_reason: string) => {
  return (await API.post('/storefront/recover', { error_reason })).data;
};

export const confirmPurchase = async (cart_id: string) => {
  return (await API.post('/storefront/confirm', { cart_id })).data;
};
