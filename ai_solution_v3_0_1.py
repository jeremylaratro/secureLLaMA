import os
from typing import List, Optional
import torch
from llama import Dialog, Llama
import gradio as gr
import fire

# Set environment variable to reduce memory fragmentation
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

def truncate_context(dialog: List[Dialog], max_tokens: int) -> List[Dialog]:
    """Truncates the dialog context to ensure it doesn't exceed max_tokens."""
    def count_tokens(dialog: List[Dialog]) -> int:
        return sum(len(message["content"].split()) for message in dialog)

    while count_tokens(dialog) > max_tokens:
        dialog.pop(0)  # Remove the oldest message
    return dialog


def clear_cache():
    """Clear GPU memory proactively and efficiently."""
    torch.cuda.synchronize()  # Ensure all computations are complete
    torch.cuda.empty_cache()  # Free unallocated memory


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
        token_limit: int = 1000,  # Maximum tokens in the dialog history
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.max_gen_len = max_gen_len
        self.token_limit = token_limit
        self.dialog: List[Dialog] = []

        # Initialize the generator
        self.generator = Llama.build(
            ckpt_dir=ckpt_dir,
            tokenizer_path=tokenizer_path,
            max_seq_len=max_seq_len,
            max_batch_size=max_batch_size,
        )
        print("[System]: Generator initialized successfully.")

    def chat(self, user_input: str) -> str:
        """Handles the chat interactions."""
        self.dialog.append({"role": "user", "content": user_input})

        # Generate a response
        try:
            results = self.generator.chat_completion(
                [self.dialog],
                max_gen_len=self.max_gen_len,
                temperature=self.temperature,
                top_p=self.top_p,
            )
        except torch.cuda.OutOfMemoryError:
            clear_cache()
            return "[Error]: CUDA out of memory. Please try again."
        except Exception as e:
            return f"[Error]: chat_completion failed: {e}"

        # Process the response
        if not results or not isinstance(results, list):
            return "[Error]: Unexpected results format."

        try:
            response = results[0]["generation"]["content"].strip()
        except (IndexError, KeyError, TypeError):
            return "[Error]: Failed to extract response content."

        # Extract the summary portion of the response
        start_marker = "summary"
        start_idx = response.lower().find(start_marker)
        if start_idx != -1:
            summary = response[start_idx:].strip()
            self.dialog.append({"role": "assistant", "content": summary})
        else:
            self.dialog.append({"role": "assistant", "content": response})

        # Truncate the dialog context
        if len(self.dialog) > 850:
            self.dialog = truncate_context(self.dialog, self.token_limit)

        return response


def gradio_chat(user_input, chat_history, llama_chat):
    """Interactive chat function for Gradio."""
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

    # Gradio UI components
    with gr.Blocks() as demo:
        chat_history = gr.State([])  # Chat history state

        # Add custom height to the chatbot using a wrapping container
        chatbot = gr.Chatbot(label="Llama Chatbot", elem_id="chatbot")
        user_input = gr.Textbox(
            label="Your Input",
            placeholder="Type your message here...",
            lines=2,
        )
        send_button = gr.Button("Send")

        def process_message(user_input, chat_history):
            """Handles message processing and clears the input."""
            new_history, updated_chat = gradio_chat(user_input, chat_history, llama_chat)
            return updated_chat, new_history, ""  # Clear the input

        # "Enter" Key to Submit
        user_input.submit(
            process_message,
            inputs=[user_input, chat_history],
            outputs=[chatbot, chat_history, user_input],
        )

        # Button Click to Submit
        send_button.click(
            process_message,
            inputs=[user_input, chat_history],
            outputs=[chatbot, chat_history, user_input],
        )

    # Custom CSS for chatbot size
    demo.css = """
    #chatbot {
        height: 600px; /* Set the height of the chatbot */
        overflow-y: auto; /* Allow vertical scrolling */
    }
    """

    # Launch Gradio on 0.0.0.0
    demo.launch(server_name="0.0.0.0", server_port=7860)


if __name__ == "__main__":
    fire.Fire(launch_gradio)
