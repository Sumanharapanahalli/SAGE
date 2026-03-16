{{/*
==============================================================================
SAGE Helm Chart — Template Helpers
==============================================================================
This file is evaluated first and provides named templates reused throughout
all other templates. Helm's include function calls these by name.
==============================================================================
*/}}

{{/*
Expand the chart name, trimmed to 63 chars (DNS label limit).
*/}}
{{- define "sage.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Generate a full release name: <release>-<chart>.
If the release name already contains the chart name, use just the release name
to avoid duplication (e.g. "sage-sage" → "sage").
*/}}
{{- define "sage.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Chart label: name-version. Used by the helm.sh/chart selector label.
*/}}
{{- define "sage.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels applied to every resource.
Keeping these consistent allows kubectl and Helm to find/diff resources reliably.
*/}}
{{- define "sage.labels" -}}
helm.sh/chart: {{ include "sage.chart" . }}
{{ include "sage.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels — the minimal stable set used in matchLabels.
Do NOT change these after first deploy; it will break rolling updates.
*/}}
{{- define "sage.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sage.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Backend-specific selector labels.
*/}}
{{- define "sage.backend.selectorLabels" -}}
{{ include "sage.selectorLabels" . }}
app.kubernetes.io/component: backend
{{- end }}

{{/*
Frontend-specific selector labels.
*/}}
{{- define "sage.frontend.selectorLabels" -}}
{{ include "sage.selectorLabels" . }}
app.kubernetes.io/component: frontend
{{- end }}

{{/*
ServiceAccount name.
If serviceAccount.name is set, use it; otherwise derive from fullname.
*/}}
{{- define "sage.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "sage.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Backend deployment name.
*/}}
{{- define "sage.backend.fullname" -}}
{{- printf "%s-backend" (include "sage.fullname" .) }}
{{- end }}

{{/*
Frontend deployment name.
*/}}
{{- define "sage.frontend.fullname" -}}
{{- printf "%s-frontend" (include "sage.fullname" .) }}
{{- end }}
