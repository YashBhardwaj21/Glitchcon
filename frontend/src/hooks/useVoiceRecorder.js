import { useState, useRef } from "react";

const GROQ_API_KEY = import.meta.env.VITE_GROQ_API_KEY;

export const useVoiceRecorder = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.start();
      setIsRecording(true);
    } catch (error) {
      console.error("Error accessing microphone:", error);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, {
          type: "audio/webm",
        });
        return audioBlob;
      };
    }
  };

  const transcribeAudio = async (audioBlob) => {
    setIsTranscribing(true);
    try {
      console.log(
        "[Transcribe] Starting transcription with blob size:",
        audioBlob.size,
      );
      const formData = new FormData();
      formData.append("file", audioBlob, "audio.webm");
      formData.append("model", "whisper-large-v3-turbo");

      const response = await fetch(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${GROQ_API_KEY}`,
          },
          body: formData,
        },
      );

      if (!response.ok) {
        throw new Error(`Transcription failed: ${response.statusText}`);
      }

      const data = await response.json();
      console.log("[Transcribe] Response from Groq:", data);
      console.log("[Transcribe] Extracted text:", data.text || "");
      return data.text || "";
    } catch (error) {
      console.error("Transcription error:", error);
      throw error;
    } finally {
      setIsTranscribing(false);
    }
  };

  const recordAndTranscribe = async () => {
    return new Promise((resolve) => {
      startRecording();

      const stopHandler = async () => {
        stopRecording();
        setTimeout(async () => {
          const audioBlob = new Blob(audioChunksRef.current, {
            type: "audio/webm",
          });
          try {
            const text = await transcribeAudio(audioBlob);
            resolve(text);
          } catch {
            resolve(""); // Return empty string on error
          }
        }, 500);
      };

      // Store handler for cleanup
      mediaRecorderRef.current._stopHandler = stopHandler;
    });
  };

  return {
    isRecording,
    isTranscribing,
    startRecording,
    stopRecording,
    recordAndTranscribe,
    transcribeAudio,
    audioChunksRef,
  };
};
