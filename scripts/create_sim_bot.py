#!/usr/bin/env python3
"""Create (or repair) the simulator's Cognito user ``sim-bot@earshot.test`` (CONTEXT §9, §7.2).

Owner: M1 · Tracker: M1-03 · Used by: the simulator's ``run`` mode (M3-06), which logs in
as this user through the ``sim`` app client.

    python scripts/create_sim_bot.py --stage <stage>                      # create or repair
    python scripts/create_sim_bot.py --stage <stage> --generate-password  # first time only

For prod, put ``AWS_PROFILE=earshot-prod`` in front. Deploy the base stack first: the
script reads the user pool id from SSM ``/earshot/<stage>/cognito/user-pool-id``.

What it does (safe to run again; it never creates a second user):
1. Reads the password from SSM SecureString ``/earshot/<stage>/sim/password``. With
   ``--generate-password`` and no parameter yet, it makes a random one and stores it there.
2. Creates the user if it's missing (email marked verified, no invitation email).
3. Sets that password as permanent, so the first login doesn't ask for a new one.
4. Adds the user to the ``simulator`` group.

The password is never printed.
"""

from __future__ import annotations

import argparse
import secrets
import string
import sys
from pathlib import Path
from typing import Any

_SERVICES_DIR = str(Path(__file__).resolve().parents[1] / "services")
if _SERVICES_DIR not in sys.path:
    sys.path.insert(0, _SERVICES_DIR)

from shared import names  # noqa: E402

SIM_USERNAME = "sim-bot@earshot.test"  # same as simulator/__main__.py
SIM_GROUP = "simulator"
PASSWORD_LENGTH = 32
_SYMBOLS = "!#%*+-=?@^_"


def generate_password(length: int = PASSWORD_LENGTH) -> str:
    """A random password that meets Cognito's default policy: at least one lowercase and
    uppercase letter, digit and symbol."""
    classes = [string.ascii_lowercase, string.ascii_uppercase, string.digits, _SYMBOLS]
    alphabet = "".join(classes)
    chars = [secrets.choice(c) for c in classes]
    chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def read_or_create_password(ssm: Any, parameter: str, *, generate: bool) -> tuple[str, bool]:
    """Return ``(password, created)``. Creates the SecureString only when it's missing and
    ``generate`` is set; it never overwrites an existing password. Raises ``LookupError``
    when the parameter is missing and ``generate`` isn't set."""
    try:
        value = ssm.get_parameter(Name=parameter, WithDecryption=True)["Parameter"]["Value"]
        return value, False
    except ssm.exceptions.ParameterNotFound:
        if not generate:
            raise LookupError(parameter) from None
    password = generate_password()
    ssm.put_parameter(Name=parameter, Value=password, Type="SecureString", Overwrite=False)
    return password, True


def ensure_sim_bot(cognito: Any, pool_id: str, password: str, username: str = SIM_USERNAME) -> bool:
    """Make sure ``username`` exists with ``password`` (permanent) and is in the
    ``simulator`` group. Returns True if the user was created now."""
    created = False
    try:
        cognito.admin_get_user(UserPoolId=pool_id, Username=username)
    except cognito.exceptions.UserNotFoundException:
        cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=username,
            UserAttributes=[
                {"Name": "email", "Value": username},
                {"Name": "email_verified", "Value": "true"},
            ],
            MessageAction="SUPPRESS",
        )
        created = True
    cognito.admin_set_user_password(UserPoolId=pool_id, Username=username, Password=password, Permanent=True)
    cognito.admin_add_user_to_group(UserPoolId=pool_id, Username=username, GroupName=SIM_GROUP)
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or repair the sim-bot Cognito user (CONTEXT §9).")
    parser.add_argument("--stage", required=True, help="e.g. tanishqa or prod")
    parser.add_argument(
        "--generate-password",
        action="store_true",
        help="if /earshot/<stage>/sim/password doesn't exist, create it with a random password",
    )
    args = parser.parse_args(argv)
    try:
        names.validate_stage(args.stage)
    except ValueError as err:
        parser.error(str(err))

    import boto3

    ssm = boto3.client("ssm", region_name=names.REGION)
    cognito = boto3.client("cognito-idp", region_name=names.REGION)

    pool_param = names.ssm_user_pool_id(args.stage)
    try:
        pool_id = ssm.get_parameter(Name=pool_param)["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        print(f"{pool_param} doesn't exist. Deploy the base stack first.", file=sys.stderr)
        return 1

    password_param = names.ssm_sim_password(args.stage)
    try:
        password, generated = read_or_create_password(ssm, password_param, generate=args.generate_password)
    except LookupError:
        print(
            f"{password_param} doesn't exist. Run again with --generate-password to create it.",
            file=sys.stderr,
        )
        return 1

    created = ensure_sim_bot(cognito, pool_id, password)

    if generated:
        print(f"Stored a new random password in {password_param} (SecureString).")
    print(f"{SIM_USERNAME}: {'created' if created else 'already existed'}; password set from SSM; in group '{SIM_GROUP}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
