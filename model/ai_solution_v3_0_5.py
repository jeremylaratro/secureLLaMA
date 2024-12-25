# File: llama_chatbot_fixed.py

import os
from typing import List, Optional
import torch
from llama import Dialog, Llama
import gradio as gr
import fire

# Set up environment variable to manage GPU memory allocation
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

def truncate_context(dialog: List[Dialog], max_tokens: int) -> List[Dialog]:
    """Keep the dialog history under the max token limit by removing the oldest messages."""
    def count_tokens(dialog: List[Dialog]) -> int:
        return sum(len(message["content"].split()) for message in dialog)

    while count_tokens(dialog) > max_tokens:
        removed_message = dialog.pop(0)  # Drop the oldest message
        print(f"[Debug] Removed message to stay within token limit: {removed_message}")
    return dialog


def clear_cache():
    """Proactively free up GPU memory to avoid out-of-memory errors."""
    torch.cuda.synchronize()
    torch.cuda.empty_cache()


class LlamaChat:
    def __init__(
        self,
        ckpt_dir: str,
        tokenizer_path: str,
        temperature: float = 0.6,
        top_p: float = 0.9,
        max_seq_len: int = 512,
        max_batch_size: int = 1,
        max_gen_len: Optional[int] = None,
        token_limit: int = 1000,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.max_gen_len = max_gen_len
        self.token_limit = token_limit
        self.dialog: List[Dialog] = []

        # Initialize the Llama generator
        self.generator = Llama.build(
            ckpt_dir=ckpt_dir,
            tokenizer_path=tokenizer_path,
            max_seq_len=max_seq_len,
            max_batch_size=max_batch_size,
        )
        print("[System]: Generator initialized successfully.")

    def chat(self, user_input: str) -> str:
        """Process user input and generate a response."""
        directive = "\n[Please provide a summary of the response in 50 words OR LESS. Include it at the END of the response. Start the summary with the word 'summary' on a newline without quotes.]"
        user_input_with_directive = user_input + directive

        # Generate a response using the directive-enhanced input
        try:
            results = self.generator.chat_completion(
                [self.dialog + [{"role": "user", "content": user_input_with_directive}]],
                max_gen_len=self.max_gen_len,
                temperature=self.temperature,
                top_p=self.top_p,
            )
        except torch.cuda.OutOfMemoryError:
            clear_cache()
            return "[Error]: CUDA ran out of memory. Try again later."
        except Exception as e:
            return f"[Error]: Failed to generate a response: {e}"

        if not results or not isinstance(results, list):
            return "[Error]: Received an invalid response format."

        try:
            response = results[0]["generation"]["content"].strip()
        except (IndexError, KeyError, TypeError):
            return "[Error]: Unable to extract content from the response."

        # Extract or truncate the summary
        summary = self._extract_summary(response)
        self.dialog.append({"role": "assistant", "content": summary})
        print(f"[Debug] Summary added to dialog: {summary}")

        # Monitor the current dialog state
#        print(f"[Debug] Current dialog context: {self.dialog}")

        # Remove old messages if the history exceeds token limits
        self.dialog = truncate_context(self.dialog, self.token_limit)
        print(f"[Debug] Updated dialog context after truncation: {self.dialog}")

        return response

    def _extract_summary(self, response: str) -> str:
        """Extract the 50-word summary from the response."""
        start_marker = "summary"
        start_idx = response.lower().find(start_marker)
        if start_idx != -1:
            if len(response) < 10:
                return " ".join(response.split()[:50])
            else:
                return response[start_idx:].strip()
        return " ".join(response.split()[:50])


def gradio_chat(user_input, chat_history, llama_chat):
    """Handle chat interactions for the Gradio interface."""
    response = llama_chat.chat(user_input)
    chat_history.append((user_input, response))
    return chat_history, chat_history


def launch_gradio(
    ckpt_dir: str,
    tokenizer_path: str,
    temperature: float = 0.6,
    top_p: float = 0.9,
    max_seq_len: int = 512,
    max_batch_size: int = 1,
    max_gen_len: Optional[int] = None,
    token_limit: int = 1000,
):
    llama_chat = LlamaChat(
        ckpt_dir=ckpt_dir,
        tokenizer_path=tokenizer_path,
        temperature=temperature,
        top_p=top_p,
        max_seq_len=max_seq_len,
        max_batch_size=max_batch_size,
        max_gen_len=max_gen_len,
        token_limit=token_limit,
    )

    with gr.Blocks() as demo:
        chat_history = gr.State([])
        chatbot = gr.Chatbot(label="Llama Chatbot", elem_id="chatbot")
        user_input = gr.Textbox(
            label="Your Input",
            placeholder="Type your message here...",
            show_label=False,  # Hide the label for cleaner UI
        )
        send_button = gr.Button("Send")

        def process_message(user_input, chat_history):
            """Process user message and clear the input field."""
            new_history, updated_chat = gradio_chat(user_input, chat_history, llama_chat)
            return updated_chat, new_history, ""  # Clear the input field

        user_input.submit(
            process_message,
            inputs=[user_input, chat_history],
            outputs=[chatbot, chat_history, user_input],
        )
        send_button.click(
            process_message,
            inputs=[user_input, chat_history],
            outputs=[chatbot, chat_history, user_input],
        )

    demo.css = """
    #chatbot {
        height: 600px;
        overflow-y: auto;
    }
    """
    demo.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    fire.Fire(launch_gradio)
