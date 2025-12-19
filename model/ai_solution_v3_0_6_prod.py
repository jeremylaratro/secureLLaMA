import os
import sys
import signal
import logging
from typing import List, Optional, Tuple

import torch
from llama import Dialog, Llama
import gradio as gr
import fire

# Configure logging
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("securellama")

# Set up environment variable to manage GPU memory allocation
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# Configuration constants
MAX_INPUT_LENGTH = 10000
DEFAULT_TOKEN_LIMIT = 1000


def clear_cache():
    """Proactively free up GPU memory to avoid out-of-memory errors."""
    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        logger.debug("GPU cache cleared")


def graceful_shutdown(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT."""
    logger.info("Shutting down gracefully...")
    clear_cache()
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, graceful_shutdown)
signal.signal(signal.SIGINT, graceful_shutdown)


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
        token_limit: int = DEFAULT_TOKEN_LIMIT,
        enable_summarization: bool = True,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.max_gen_len = max_gen_len
        self.token_limit = token_limit
        self.enable_summarization = enable_summarization
        self.dialog: List[Dialog] = []

        # Initialize the Llama generator
        self.generator = Llama.build(
            ckpt_dir=ckpt_dir,
            tokenizer_path=tokenizer_path,
            max_seq_len=max_seq_len,
            max_batch_size=max_batch_size,
        )
        logger.info("Llama generator initialized successfully")

    def _count_tokens(self, text: str) -> int:
        """Count tokens using the actual tokenizer for accuracy."""
        try:
            # Use the generator's tokenizer for accurate token counting
            tokens = self.generator.tokenizer.encode(text, bos=False, eos=False)
            return len(tokens)
        except Exception:
            # Fallback to word-based estimation if tokenizer fails
            # Multiply by 1.3 to account for subword tokenization
            return int(len(text.split()) * 1.3)

    def _count_dialog_tokens(self) -> int:
        """Count total tokens in the dialog history."""
        total = 0
        for message in self.dialog:
            total += self._count_tokens(message["content"])
        return total

    def _truncate_context(self) -> None:
        """Keep the dialog history under the max token limit by removing oldest messages."""
        while self._count_dialog_tokens() > self.token_limit and len(self.dialog) > 0:
            removed = self.dialog.pop(0)
            logger.debug(f"Removed oldest message to stay within token limit (role: {removed['role']})")

    def _validate_input(self, user_input: str) -> Tuple[bool, str]:
        """Validate user input and return (is_valid, error_message)."""
        if not user_input or not user_input.strip():
            return False, "[Error]: Please enter a message."
        if len(user_input) > MAX_INPUT_LENGTH:
            return False, f"[Error]: Message too long. Maximum {MAX_INPUT_LENGTH} characters."
        return True, ""

    def chat(self, user_input: str) -> str:
        """Process user input and generate a response."""
        # Validate input
        is_valid, error_msg = self._validate_input(user_input)
        if not is_valid:
            return error_msg

        user_input = user_input.strip()

        # Add user message to dialog history
        self.dialog.append({"role": "user", "content": user_input})

        # Prepare the prompt with optional summarization directive
        if self.enable_summarization:
            directive = "\n[Please provide a summary of the response in 50 words or less at the end, starting with 'Summary:' on a new line.]"
            prompt_content = user_input + directive
        else:
            prompt_content = user_input

        # Build the full dialog for generation (with directive only in the latest message)
        generation_dialog = self.dialog[:-1] + [{"role": "user", "content": prompt_content}]

        # Generate a response
        try:
            results = self.generator.chat_completion(
                [generation_dialog],
                max_gen_len=self.max_gen_len,
                temperature=self.temperature,
                top_p=self.top_p,
            )
        except torch.cuda.OutOfMemoryError:
            clear_cache()
            # Remove the user message we just added since generation failed
            self.dialog.pop()
            return "[Error]: CUDA ran out of memory. Please try again with a shorter message."
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            self.dialog.pop()
            return f"[Error]: Failed to generate a response. Please try again."

        if not results or not isinstance(results, list):
            self.dialog.pop()
            return "[Error]: Received an invalid response format."

        try:
            response = results[0]["generation"]["content"].strip()
        except (IndexError, KeyError, TypeError):
            self.dialog.pop()
            return "[Error]: Unable to extract content from the response."

        # For dialog history, store a condensed version (summary if available)
        if self.enable_summarization:
            summary = self._extract_summary(response)
            self.dialog.append({"role": "assistant", "content": summary})
        else:
            # Store truncated response if too long
            max_history_len = 500
            if len(response) > max_history_len:
                self.dialog.append({"role": "assistant", "content": response[:max_history_len] + "..."})
            else:
                self.dialog.append({"role": "assistant", "content": response})

        # Truncate context if needed
        self._truncate_context()

        return response

    def _extract_summary(self, response: str) -> str:
        """Extract the summary from the response, or create one if not found."""
        # Look for summary marker (case-insensitive)
        lower_response = response.lower()

        # Try different summary markers
        for marker in ["summary:", "summary -", "summary\n"]:
            idx = lower_response.find(marker)
            if idx != -1:
                # Extract everything after the marker
                summary_start = idx + len(marker)
                summary = response[summary_start:].strip()
                if summary:
                    return summary

        # If no summary marker found, just use marker word
        if "summary" in lower_response:
            idx = lower_response.find("summary")
            return response[idx:].strip()

        # Fallback: use first 50 words of response
        words = response.split()
        return " ".join(words[:50]) + ("..." if len(words) > 50 else "")

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.dialog = []
        clear_cache()
        logger.info("Conversation history cleared")


def gradio_chat(
    user_input: str,
    chat_history: List[Tuple[str, str]],
    llama_chat: LlamaChat
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """Handle chat interactions for the Gradio interface."""
    response = llama_chat.chat(user_input)
    chat_history.append((user_input, response))
    return chat_history, chat_history


def serve_gradio(
    ckpt_dir: str,
    tokenizer_path: str,
    temperature: float = 0.6,
    top_p: float = 0.9,
    max_seq_len: int = 512,
    max_batch_size: int = 1,
    max_gen_len: Optional[int] = None,
    token_limit: int = DEFAULT_TOKEN_LIMIT,
    enable_summarization: bool = True,
    host: str = "0.0.0.0",
    port: int = 7860,
    ssl_certfile: Optional[str] = None,
    ssl_keyfile: Optional[str] = None,
):
    """Launch the Gradio web interface for the LLaMA chatbot."""
    logger.info(f"Starting SecureLLaMA server on {host}:{port}")

    llama_chat = LlamaChat(
        ckpt_dir=ckpt_dir,
        tokenizer_path=tokenizer_path,
        temperature=temperature,
        top_p=top_p,
        max_seq_len=max_seq_len,
        max_batch_size=max_batch_size,
        max_gen_len=max_gen_len,
        token_limit=token_limit,
        enable_summarization=enable_summarization,
    )

    # Create the Gradio Interface
    with gr.Blocks(title="SecureLLaMA") as demo:
        gr.Markdown("# SecureLLaMA - Private AI Assistant")

        chat_history = gr.State([])
        chatbot = gr.Chatbot(label="Conversation", elem_id="chatbot", height=500)
        user_input = gr.Textbox(
            label="Your message",
            placeholder="Type your message here...",
            show_label=False,
            max_lines=5,
        )

        with gr.Row():
            send_button = gr.Button("Send", variant="primary")
            clear_button = gr.Button("Clear History")

        def process_message(user_input: str, chat_history: List[Tuple[str, str]]):
            """Process user message and clear the input field."""
            if not user_input.strip():
                return chat_history, chat_history, ""
            new_history, updated_chat = gradio_chat(user_input, chat_history, llama_chat)
            return updated_chat, new_history, ""

        def clear_history(chat_history: List[Tuple[str, str]]):
            """Clear the chat history."""
            llama_chat.clear_history()
            return [], []

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
        clear_button.click(
            clear_history,
            inputs=[chat_history],
            outputs=[chatbot, chat_history],
        )

    # Launch the Gradio app with optional SSL support
    ssl_enabled = ssl_certfile and ssl_keyfile
    if ssl_enabled:
        logger.info("SSL enabled")
        demo.launch(
            server_name=host,
            server_port=port,
            ssl_certfile=ssl_certfile,
            ssl_keyfile=ssl_keyfile,
        )
    else:
        logger.warning("SSL not configured - running without encryption")
        demo.launch(server_name=host, server_port=port)


if __name__ == "__main__":
    fire.Fire(serve_gradio)
