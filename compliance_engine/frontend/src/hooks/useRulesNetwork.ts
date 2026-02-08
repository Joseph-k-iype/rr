import { useQuery } from '@tanstack/react-query';
import { getRulesNetwork } from '../services/graphDataApi';

export function useRulesNetwork() {
  return useQuery({
    queryKey: ['rulesNetwork'],
    queryFn: getRulesNetwork,
    staleTime: 2 * 60 * 1000,
  });
}
