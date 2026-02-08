import api from './api';
import type { RulesOverviewResponse, DropdownValues } from '../types/api';

export async function getRulesOverview(): Promise<RulesOverviewResponse> {
  const { data } = await api.get<RulesOverviewResponse>('/rules-overview');
  return data;
}

export async function getDropdownValues(): Promise<DropdownValues> {
  const { data } = await api.get<DropdownValues>('/all-dropdown-values');
  return data;
}

export async function getCountries(): Promise<string[]> {
  const { data } = await api.get<string[]>('/countries');
  return data;
}

export async function getPurposes(): Promise<string[]> {
  const { data } = await api.get<string[]>('/purposes');
  return data;
}
