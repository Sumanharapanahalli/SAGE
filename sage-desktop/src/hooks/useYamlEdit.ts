import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as client from "@/api/client";
import type {
  DesktopError,
  YamlFileName,
  YamlReadResult,
  YamlWriteResult,
} from "@/api/types";

export const yamlKey = (file: YamlFileName) => ["yaml", file] as const;

export const useReadYaml = (file: YamlFileName | undefined) =>
  useQuery<YamlReadResult, DesktopError>({
    queryKey: yamlKey((file ?? "project") as YamlFileName),
    queryFn: () => client.readYaml(file as YamlFileName),
    enabled: Boolean(file),
    staleTime: 0,
  });

interface WriteArgs {
  file: YamlFileName;
  content: string;
}

export function useWriteYaml() {
  const qc = useQueryClient();
  return useMutation<YamlWriteResult, DesktopError, WriteArgs>({
    mutationFn: ({ file, content }) => client.writeYaml(file, content),
    onSuccess: (_data, { file }) => {
      qc.invalidateQueries({ queryKey: yamlKey(file) });
    },
  });
}
