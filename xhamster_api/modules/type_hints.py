from typing import Callable, Awaitable, Union
on_error_hint = Union[Callable[[str, Exception, int], Awaitable[bool]], None]
