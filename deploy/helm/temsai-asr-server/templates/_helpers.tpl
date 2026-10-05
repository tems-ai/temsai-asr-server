{{- define "asr.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "asr.fullname" -}}
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

{{- define "asr.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "asr.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "asr.selectorLabels" -}}
app.kubernetes.io/name: {{ include "asr.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "asr.image" -}}
{{- $tag := .Values.image.tag | default (printf "%s-%s" .Chart.AppVersion .Values.image.variant) -}}
{{- printf "%s:%s" .Values.image.repository $tag -}}
{{- end }}

{{- define "asr.apiKeySecretName" -}}
{{- .Values.apiKey.existingSecret | default (include "asr.fullname" .) -}}
{{- end }}

{{- define "asr.apiKeyEnabled" -}}
{{- if or .Values.apiKey.value .Values.apiKey.existingSecret }}true{{ end -}}
{{- end }}
