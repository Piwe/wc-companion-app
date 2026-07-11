import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

// Data changes at most once per day, so cache generously.
const DAY = 1000 * 60 * 60 * 24;

export const useTeams = (q?: string) =>
  useQuery({ queryKey: ["teams", q ?? ""], queryFn: () => api.listTeams(q), staleTime: DAY });

export const useTeamStatus = (id: number) =>
  useQuery({ queryKey: ["team", id], queryFn: () => api.teamStatus(id), staleTime: DAY });

export const useGroups = () =>
  useQuery({ queryKey: ["groups"], queryFn: () => api.listGroups(), staleTime: DAY });

export const useGroup = (name: string) =>
  useQuery({ queryKey: ["group", name], queryFn: () => api.groupDetail(name), staleTime: DAY });

export const useTeamMatches = (id: number) =>
  useQuery({ queryKey: ["team-matches", id], queryFn: () => api.teamMatches(id), staleTime: DAY });

export const useMatch = (id: number) =>
  useQuery({ queryKey: ["match", id], queryFn: () => api.matchDetail(id), staleTime: DAY });
