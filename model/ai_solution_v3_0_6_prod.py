import os
import sys
import signal
import logging
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass, field

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
DEFAULT_TOKEN_LIMIT = 6000  # Increased from 1000 - use more of the 8192 context
DEFAULT_RECENT_TURNS = 4    # Keep last N turns in full detail
DEFAULT_SUMMARY_TOKENS = 200  # Max tokens for conversation summary


@dataclass
class ConversationMemory:
    """Hierarchical memory system for long conversations.

    Structure:
    - conversation_summary: Rolling summary of older conversation (compressed)
    - recent_messages: Last N turns kept in full detail
    """
    conversation_summary: str = ""
    recent_messages: List[Dict[str, str]] = field(default_factory=list)
    total_exchanges: int = 0


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
        max_seq_len: int = 8192,  # Increased from 512 to use full context
        max_batch_size: int = 1,
        max_gen_len: Optional[int] = None,
        token_limit: int = DEFAULT_TOKEN_LIMIT,
        recent_turns: int = DEFAULT_RECENT_TURNS,
        summary_tokens: int = DEFAULT_SUMMARY_TOKENS,
    ):
        self.temperature = temperature
        self.top_p = top_p
        self.max_gen_len = max_gen_len
        self.token_limit = token_limit
        self.recent_turns = recent_turns
        self.summary_tokens = summary_tokens

        # Hierarchical memory instead of flat dialog list
        self.memory = ConversationMemory()

        # Initialize the Llama generator
        self.generator = Llama.build(
            ckpt_dir=ckpt_dir,
            tokenizer_path=tokenizer_path,
            max_seq_len=max_seq_len,
            max_batch_size=max_batch_size,
        )
        logger.info(f"Llama generator initialized (max_seq_len={max_seq_len}, token_limit={token_limit})")

    def _count_tokens(self, text: str) -> int:
        """Count tokens using the actual tokenizer for accuracy."""
        if not text:
            return 0
        try:
            tokens = self.generator.tokenizer.encode(text, bos=False, eos=False)
            return len(tokens)
        except Exception:
            return int(len(text.split()) * 1.3)

    def _count_memory_tokens(self) -> int:
        """Count total tokens in the memory system."""
        total = self._count_tokens(self.memory.conversation_summary)
        for message in self.memory.recent_messages:
            total += self._count_tokens(message["content"])
        return total

    def _build_context(self) -> List[Dict[str, str]]:
        """Build the dialog context from hierarchical memory."""
        context = []

        # Add conversation summary as system context if it exists
        if self.memory.conversation_summary:
            context.append({
                "role": "system",
                "content": f"Previous conversation summary: {self.memory.conversation_summary}"
            })

        # Add recent messages in full detail
        context.extend(self.memory.recent_messages)

        return context

    def _compress_old_messages(self) -> None:
        """Compress older messages into the conversation summary."""
        # Keep only the most recent turns
        messages_per_turn = 2  # user + assistant
        max_recent = self.recent_turns * messages_per_turn

        if len(self.memory.recent_messages) <= max_recent:
            return

        # Messages to compress (oldest ones beyond recent_turns)
        to_compress = self.memory.recent_messages[:-max_recent]
        self.memory.recent_messages = self.memory.recent_messages[-max_recent:]

        # Build summary of compressed messages
        compressed_text = self._summarize_messages(to_compress)

        # Merge with existing summary
        if self.memory.conversation_summary:
            self.memory.conversation_summary = self._merge_summaries(
                self.memory.conversation_summary,
                compressed_text
            )
        else:
            self.memory.conversation_summary = compressed_text

        logger.debug(f"Compressed {len(to_compress)} messages into summary")

    def _summarize_messages(self, messages: List[Dict[str, str]]) -> str:
        """Create a brief summary of messages for compression."""
        # Format messages for summarization
        formatted = []
        for msg in messages:
            role = "User" if msg["role"] == "user" else "Assistant"
            # Truncate long messages
            content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
            formatted.append(f"{role}: {content}")

        messages_text = "\n".join(formatted)

        # Use the model to summarize if we have enough content
        if self._count_tokens(messages_text) > 100:
            try:
                summary_prompt = [{
                    "role": "user",
                    "content": f"Summarize this conversation in 2-3 sentences, focusing on key topics and decisions:\n\n{messages_text}"
                }]

                result = self.generator.chat_completion(
                    [summary_prompt],
                    max_gen_len=100,
                    temperature=0.3,  # Lower temperature for factual summary
                    top_p=0.9,
                )

                if result and isinstance(result, list):
                    return result[0]["generation"]["content"].strip()
            except Exception as e:
                logger.warning(f"Failed to generate summary: {e}")

        # Fallback: just concatenate truncated messages
        return " | ".join([m["content"][:50] for m in messages])

    def _merge_summaries(self, old_summary: str, new_summary: str) -> str:
        """Merge old and new summaries, keeping under token limit."""
        combined = f"{old_summary} Additionally: {new_summary}"

        # If combined is too long, summarize the summaries
        if self._count_tokens(combined) > self.summary_tokens:
            try:
                merge_prompt = [{
                    "role": "user",
                    "content": f"Combine these summaries into one concise summary (max 3 sentences):\n\n1. {old_summary}\n2. {new_summary}"
                }]

                result = self.generator.chat_completion(
                    [merge_prompt],
                    max_gen_len=100,
                    temperature=0.3,
                    top_p=0.9,
                )

                if result and isinstance(result, list):
                    return result[0]["generation"]["content"].strip()
            except Exception as e:
                logger.warning(f"Failed to merge summaries: {e}")

            # Fallback: truncate old summary and append new
            old_words = old_summary.split()[:30]
            return " ".join(old_words) + "... " + new_summary

        return combined

    def _validate_input(self, user_input: str) -> Tuple[bool, str]:
        """Validate user input and return (is_valid, error_message)."""
        if not user_input or not user_input.strip():
            return False, "[Error]: Please enter a message."
        if len(user_input) > MAX_INPUT_LENGTH:
            return False, f"[Error]: Message too long. Maximum {MAX_INPUT_LENGTH} characters."
        return True, ""

    def _condense_response(self, response: str) -> str:
        """Condense a response for storage in recent messages."""
        # Keep responses under 300 chars for storage efficiency
        max_len = 300
        if len(response) <= max_len:
            return response

        # Try to find a natural break point
        truncated = response[:max_len]
        last_period = truncated.rfind('.')
        last_newline = truncated.rfind('\n')
        break_point = max(last_period, last_newline)

        if break_point > max_len // 2:
            return response[:break_point + 1].strip()

        return truncated.strip() + "..."

    def chat(self, user_input: str) -> str:
        """Process user input and generate a response."""
        # Validate input
        is_valid, error_msg = self._validate_input(user_input)
        if not is_valid:
            return error_msg

        user_input = user_input.strip()

        # Compress old messages before adding new ones
        self._compress_old_messages()

        # Add user message to recent messages (condensed for storage)
        user_condensed = user_input[:300] + "..." if len(user_input) > 300 else user_input
        self.memory.recent_messages.append({"role": "user", "content": user_condensed})

        # Build context from hierarchical memory
        context = self._build_context()

        # For generation, use full user input (not condensed)
        generation_context = context[:-1] + [{"role": "user", "content": user_input}]

        # Check token budget before generation
        context_tokens = sum(self._count_tokens(m["content"]) for m in generation_context)
        available_for_response = self.token_limit - context_tokens - 100  # Buffer

        if available_for_response < 100:
            # Emergency compression
            logger.warning("Token budget critical, forcing compression")
            self._force_compression()
            context = self._build_context()
            generation_context = context[:-1] + [{"role": "user", "content": user_input}]

        # Generate response
        try:
            results = self.generator.chat_completion(
                [generation_context],
                max_gen_len=min(self.max_gen_len or 1024, available_for_response),
                temperature=self.temperature,
                top_p=self.top_p,
            )
        except torch.cuda.OutOfMemoryError:
            clear_cache()
            self.memory.recent_messages.pop()  # Remove the user message we just added
            return "[Error]: CUDA ran out of memory. Please try again with a shorter message."
        except Exception as e:
            logger.error(f"Generation failed: {e}")
            self.memory.recent_messages.pop()
            return "[Error]: Failed to generate a response. Please try again."

        if not results or not isinstance(results, list):
            self.memory.recent_messages.pop()
            return "[Error]: Received an invalid response format."

        try:
            response = results[0]["generation"]["content"].strip()
        except (IndexError, KeyError, TypeError):
            self.memory.recent_messages.pop()
            return "[Error]: Unable to extract content from the response."

        # Store condensed response in memory
        condensed = self._condense_response(response)
        self.memory.recent_messages.append({"role": "assistant", "content": condensed})

        self.memory.total_exchanges += 1

        # Log memory status periodically
        if self.memory.total_exchanges % 5 == 0:
            tokens_used = self._count_memory_tokens()
            logger.info(f"Memory status: {tokens_used}/{self.token_limit} tokens, "
                       f"{len(self.memory.recent_messages)} recent messages, "
                       f"{self.memory.total_exchanges} total exchanges")

        return response

    def _force_compression(self) -> None:
        """Force aggressive compression when running out of tokens."""
        # Keep only the last 2 turns
        messages_per_turn = 2
        keep = 2 * messages_per_turn

        if len(self.memory.recent_messages) > keep:
            to_compress = self.memory.recent_messages[:-keep]
            self.memory.recent_messages = self.memory.recent_messages[-keep:]

            # Quick compression without LLM
            compressed = " | ".join([m["content"][:30] for m in to_compress])
            if self.memory.conversation_summary:
                self.memory.conversation_summary = self.memory.conversation_summary[:100] + " | " + compressed
            else:
                self.memory.conversation_summary = compressed

        # Also truncate summary if needed
        if self._count_tokens(self.memory.conversation_summary) > self.summary_tokens:
            words = self.memory.conversation_summary.split()[:50]
            self.memory.conversation_summary = " ".join(words) + "..."

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.memory = ConversationMemory()
        clear_cache()
        logger.info("Conversation history cleared")

    def get_memory_stats(self) -> Dict:
        """Get current memory statistics."""
        return {
            "total_tokens": self._count_memory_tokens(),
            "token_limit": self.token_limit,
            "recent_messages": len(self.memory.recent_messages),
            "has_summary": bool(self.memory.conversation_summary),
            "total_exchanges": self.memory.total_exchanges,
        }


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
    max_seq_len: int = 8192,  # Increased default
    max_batch_size: int = 1,
    max_gen_len: Optional[int] = None,
    token_limit: int = DEFAULT_TOKEN_LIMIT,
    recent_turns: int = DEFAULT_RECENT_TURNS,
    summary_tokens: int = DEFAULT_SUMMARY_TOKENS,
    host: str = "0.0.0.0",
    port: int = 7860,
    ssl_certfile: Optional[str] = None,
    ssl_keyfile: Optional[str] = None,
):
    """Launch the Gradio web interface for the LLaMA chatbot.

    Args:
        ckpt_dir: Path to model checkpoint directory
        tokenizer_path: Path to tokenizer model file
        temperature: Sampling temperature (0.0-1.0)
        top_p: Nucleus sampling parameter
        max_seq_len: Maximum sequence length for the model
        max_batch_size: Batch size for inference
        max_gen_len: Maximum generation length (None for auto)
        token_limit: Maximum tokens to keep in context (default: 6000)
        recent_turns: Number of recent conversation turns to keep in full (default: 4)
        summary_tokens: Maximum tokens for conversation summary (default: 200)
        host: Server host address
        port: Server port
        ssl_certfile: Path to SSL certificate file
        ssl_keyfile: Path to SSL key file
    """
    logger.info(f"Starting SecureLLaMA server on {host}:{port}")
    logger.info(f"Context settings: token_limit={token_limit}, recent_turns={recent_turns}")

    llama_chat = LlamaChat(
        ckpt_dir=ckpt_dir,
        tokenizer_path=tokenizer_path,
        temperature=temperature,
        top_p=top_p,
        max_seq_len=max_seq_len,
        max_batch_size=max_batch_size,
        max_gen_len=max_gen_len,
        token_limit=token_limit,
        recent_turns=recent_turns,
        summary_tokens=summary_tokens,
    )

    # Create the Gradio Interface
    with gr.Blocks(title="SecureLLaMA") as demo:
        gr.Markdown("# SecureLLaMA - Private AI Assistant")
        gr.Markdown("*Featuring hierarchical memory for extended conversations*")

        chat_history = gr.State([])
        chatbot = gr.Chatbot(label="Conversation", elem_id="chatbot", height=500)

        with gr.Row():
            user_input = gr.Textbox(
                label="Your message",
                placeholder="Type your message here...",
                show_label=False,
                max_lines=5,
                scale=4,
            )
            send_button = gr.Button("Send", variant="primary", scale=1)

        with gr.Row():
            clear_button = gr.Button("Clear History")
            stats_button = gr.Button("Show Memory Stats")

        stats_output = gr.Textbox(label="Memory Statistics", visible=False)

        def process_message(user_input: str, chat_history: List[Tuple[str, str]]):
            """Process user message and clear the input field."""
            if not user_input.strip():
                return chat_history, chat_history, ""
            new_history, updated_chat = gradio_chat(user_input, chat_history, llama_chat)
            return updated_chat, new_history, ""

        def clear_history_fn(chat_history: List[Tuple[str, str]]):
            """Clear the chat history."""
            llama_chat.clear_history()
            return [], []

        def show_stats():
            """Show memory statistics."""
            stats = llama_chat.get_memory_stats()
            return gr.update(
                visible=True,
                value=f"Tokens: {stats['total_tokens']}/{stats['token_limit']} | "
                      f"Recent messages: {stats['recent_messages']} | "
                      f"Has summary: {stats['has_summary']} | "
                      f"Total exchanges: {stats['total_exchanges']}"
            )

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
            clear_history_fn,
            inputs=[chat_history],
            outputs=[chatbot, chat_history],
        )
        stats_button.click(
            show_stats,
            outputs=[stats_output],
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
