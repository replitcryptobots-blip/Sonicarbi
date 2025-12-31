// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {IPool} from "@aave/core-v3/contracts/interfaces/IPool.sol";
import {IFlashLoanSimpleReceiver} from "@aave/core-v3/contracts/flashloan/interfaces/IFlashLoanSimpleReceiver.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import {SafeERC20} from "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";

/**
 * @title FlashloanArbitrage
 * @notice Executes DEX arbitrage opportunities using Aave V3 flashloans on Scroll
 * @dev Implements IFlashLoanSimpleReceiver for Aave V3 flashloan integration
 *
 * Security features:
 * - Owner-only execution
 * - Reentrancy protection
 * - Emergency pause mechanism
 * - Slippage protection
 * - Profit verification
 */
contract FlashloanArbitrage is IFlashLoanSimpleReceiver, Ownable, ReentrancyGuard, Pausable {
    using SafeERC20 for IERC20;

    /// @notice Aave V3 Pool address on Scroll
    IPool public immutable POOL;

    /// @notice Uniswap V2 Router interface (minimal)
    interface IUniswapV2Router {
        function swapExactTokensForTokens(
            uint256 amountIn,
            uint256 amountOutMin,
            address[] calldata path,
            address to,
            uint256 deadline
        ) external returns (uint256[] memory amounts);

        function getAmountsOut(uint256 amountIn, address[] calldata path)
            external
            view
            returns (uint256[] memory amounts);
    }

    /// @notice Arbitrage execution parameters
    struct ArbitrageParams {
        address tokenBorrow;      // Token to flashloan
        uint256 amount;           // Amount to borrow
        address tokenTarget;      // Token to swap to (for 2-hop routes)
        address buyDex;           // DEX to buy on (router address)
        address sellDex;          // DEX to sell on (router address)
        address[] buyPath;        // Full path for buy swap (if multi-hop)
        address[] sellPath;       // Full path for sell swap (if multi-hop)
        uint256 minProfit;        // Minimum profit in tokenBorrow
        uint256 deadline;         // Transaction deadline
        uint256 slippageBps;      // Maximum slippage in basis points (e.g., 200 = 2%)
    }

    /// @notice Maximum allowed slippage (5% in basis points)
    uint256 public constant MAX_SLIPPAGE_BPS = 500;

    /// @notice Maximum trade size (in wei, adjustable by owner)
    uint256 public maxTradeSize = type(uint256).max;

    /// @notice Minimum profit threshold (in wei, adjustable by owner)
    uint256 public minProfitThreshold = 0;

    /// @notice Events
    event ArbitrageExecuted(
        address indexed tokenBorrow,
        address indexed tokenTarget,
        uint256 amountBorrowed,
        uint256 profit,
        address buyDex,
        address sellDex,
        uint256 buyPathLength,
        uint256 sellPathLength
    );

    event ProfitWithdrawn(address indexed token, uint256 amount, address indexed to);

    event MaxTradeSizeUpdated(uint256 oldSize, uint256 newSize);

    event MinProfitThresholdUpdated(uint256 oldThreshold, uint256 newThreshold);

    /// @notice Errors
    error InsufficientProfit(uint256 actual, uint256 required);
    error UnauthorizedFlashLoan();
    error ArbitrageFailed(string reason);
    error TradeSizeTooLarge(uint256 amount, uint256 maxAllowed);
    error InvalidPath(string reason);
    error InvalidRouter(address router);

    /**
     * @notice Constructor
     * @param _pool Aave V3 Pool address
     */
    constructor(address _pool) Ownable(msg.sender) {
        require(_pool != address(0), "Invalid pool address");
        POOL = IPool(_pool);
    }

    /**
     * @notice Execute arbitrage opportunity
     * @param params Arbitrage parameters
     */
    function executeArbitrage(ArbitrageParams calldata params)
        external
        onlyOwner
        whenNotPaused
        nonReentrant
    {
        // Input validation
        require(params.amount > 0, "Invalid amount");
        require(params.buyDex != address(0), "Invalid buy DEX");
        require(params.sellDex != address(0), "Invalid sell DEX");
        require(params.buyDex != params.sellDex, "Same DEX");
        require(params.deadline >= block.timestamp, "Deadline passed");
        require(params.slippageBps <= MAX_SLIPPAGE_BPS, "Slippage too high");

        // Trade size limit
        if (params.amount > maxTradeSize) {
            revert TradeSizeTooLarge(params.amount, maxTradeSize);
        }

        // Validate paths if provided
        if (params.buyPath.length > 0) {
            _validatePath(params.buyPath, params.tokenBorrow, params.tokenTarget);
        }
        if (params.sellPath.length > 0) {
            _validatePath(params.sellPath, params.tokenTarget, params.tokenBorrow);
        }

        // Encode parameters for flashloan callback
        bytes memory encodedParams = abi.encode(params);

        // Request flashloan from Aave V3
        POOL.flashLoanSimple(
            address(this),
            params.tokenBorrow,
            params.amount,
            encodedParams,
            0 // referralCode
        );
    }

    /**
     * @notice Aave V3 flashloan callback
     * @param asset The address of the flash-borrowed asset
     * @param amount The amount flash-borrowed
     * @param premium The fee flash-borrowed
     * @param initiator The address that initiated the flashloan
     * @param params Encoded arbitrage parameters
     * @return True if the execution of the operation succeeds
     */
    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        // Ensure this is called by the Aave Pool
        if (msg.sender != address(POOL)) {
            revert UnauthorizedFlashLoan();
        }

        // Ensure this contract initiated the flashloan
        if (initiator != address(this)) {
            revert UnauthorizedFlashLoan();
        }

        // Decode parameters
        ArbitrageParams memory arbParams = abi.decode(params, (ArbitrageParams));

        // Verify asset matches
        require(asset == arbParams.tokenBorrow, "Asset mismatch");

        // Execute arbitrage
        uint256 profit = _executeArbitrage(arbParams, amount);

        // Calculate total amount to repay (borrowed + premium)
        uint256 totalDebt = amount + premium;

        // Ensure we have enough to repay and meet minimum profit
        uint256 finalBalance = IERC20(asset).balanceOf(address(this));

        if (finalBalance < totalDebt) {
            revert ArbitrageFailed("Insufficient funds to repay loan");
        }

        uint256 netProfit = finalBalance - totalDebt;

        if (netProfit < arbParams.minProfit) {
            revert InsufficientProfit(netProfit, arbParams.minProfit);
        }

        // Check global minimum profit threshold
        if (netProfit < minProfitThreshold) {
            revert InsufficientProfit(netProfit, minProfitThreshold);
        }

        // Approve the Pool to pull the total debt
        IERC20(asset).safeIncreaseAllowance(address(POOL), totalDebt);

        emit ArbitrageExecuted(
            arbParams.tokenBorrow,
            arbParams.tokenTarget,
            amount,
            netProfit,
            arbParams.buyDex,
            arbParams.sellDex,
            arbParams.buyPath.length > 0 ? arbParams.buyPath.length : 2,
            arbParams.sellPath.length > 0 ? arbParams.sellPath.length : 2
        );

        return true;
    }

    /**
     * @notice Internal arbitrage execution logic
     * @param params Arbitrage parameters
     * @param amount Amount borrowed
     * @return profit Net profit from arbitrage
     */
    function _executeArbitrage(ArbitrageParams memory params, uint256 amount)
        internal
        returns (uint256)
    {
        // Step 1: Buy swap - use multi-hop if path provided, otherwise direct swap
        uint256 targetAmount;
        if (params.buyPath.length > 0) {
            targetAmount = _swapOnDexMultiHop(
                params.buyDex,
                params.buyPath,
                amount,
                params.deadline,
                params.slippageBps
            );
        } else {
            targetAmount = _swapOnDex(
                params.buyDex,
                params.tokenBorrow,
                params.tokenTarget,
                amount,
                params.deadline,
                params.slippageBps
            );
        }

        // Step 2: Sell swap - use multi-hop if path provided, otherwise direct swap
        uint256 finalAmount;
        if (params.sellPath.length > 0) {
            finalAmount = _swapOnDexMultiHop(
                params.sellDex,
                params.sellPath,
                targetAmount,
                params.deadline,
                params.slippageBps
            );
        } else {
            finalAmount = _swapOnDex(
                params.sellDex,
                params.tokenTarget,
                params.tokenBorrow,
                targetAmount,
                params.deadline,
                params.slippageBps
            );
        }

        // Return the final amount (profit will be calculated in executeOperation)
        return finalAmount;
    }

    /**
     * @notice Execute swap on Uniswap V2 compatible DEX with slippage protection
     * @param router DEX router address
     * @param tokenIn Input token
     * @param tokenOut Output token
     * @param amountIn Input amount
     * @param deadline Transaction deadline
     * @param slippageBps Maximum slippage in basis points
     * @return amountOut Output amount received
     */
    function _swapOnDex(
        address router,
        address tokenIn,
        address tokenOut,
        uint256 amountIn,
        uint256 deadline,
        uint256 slippageBps
    ) internal returns (uint256) {
        // Approve router to spend tokens
        IERC20(tokenIn).safeIncreaseAllowance(router, amountIn);

        // Setup swap path
        address[] memory path = new address[](2);
        path[0] = tokenIn;
        path[1] = tokenOut;

        // Get expected output amount
        uint256[] memory expectedAmounts = IUniswapV2Router(router).getAmountsOut(amountIn, path);
        uint256 expectedOut = expectedAmounts[1];

        // Calculate minimum output with slippage protection
        // minOut = expectedOut * (10000 - slippageBps) / 10000
        uint256 minAmountOut = (expectedOut * (10000 - slippageBps)) / 10000;

        // Execute swap with slippage protection
        uint256[] memory amounts = IUniswapV2Router(router).swapExactTokensForTokens(
            amountIn,
            minAmountOut, // Slippage-protected minimum output
            path,
            address(this),
            deadline
        );

        // Reset allowance to 0 for security (prevent lingering approvals)
        IERC20(tokenIn).forceApprove(router, 0);

        return amounts[amounts.length - 1];
    }

    /**
     * @notice Execute multi-hop swap on Uniswap V2 compatible DEX
     * @param router DEX router address
     * @param path Full swap path (e.g., [tokenA, tokenB, tokenC])
     * @param amountIn Input amount
     * @param deadline Transaction deadline
     * @param slippageBps Maximum slippage in basis points
     * @return amountOut Final output amount received
     */
    function _swapOnDexMultiHop(
        address router,
        address[] memory path,
        uint256 amountIn,
        uint256 deadline,
        uint256 slippageBps
    ) internal returns (uint256) {
        require(path.length >= 2, "Path too short");
        require(path.length <= 4, "Path too long");  // Limit to 3 hops max

        // Approve router to spend input tokens
        IERC20(path[0]).safeIncreaseAllowance(router, amountIn);

        // Get expected output amount
        uint256[] memory expectedAmounts = IUniswapV2Router(router).getAmountsOut(amountIn, path);
        uint256 expectedOut = expectedAmounts[expectedAmounts.length - 1];

        // Calculate minimum output with slippage protection
        uint256 minAmountOut = (expectedOut * (10000 - slippageBps)) / 10000;

        // Execute multi-hop swap with slippage protection
        uint256[] memory amounts = IUniswapV2Router(router).swapExactTokensForTokens(
            amountIn,
            minAmountOut,
            path,
            address(this),
            deadline
        );

        // Reset allowance to 0 for security (prevent lingering approvals)
        IERC20(path[0]).forceApprove(router, 0);

        return amounts[amounts.length - 1];
    }

    /**
     * @notice Validate swap path
     * @param path Swap path to validate
     * @param expectedStart Expected first token
     * @param expectedEnd Expected last token
     */
    function _validatePath(
        address[] memory path,
        address expectedStart,
        address expectedEnd
    ) internal pure {
        if (path.length < 2) {
            revert InvalidPath("Path too short");
        }
        if (path.length > 4) {
            revert InvalidPath("Path too long (max 3 hops)");
        }
        if (path[0] != expectedStart) {
            revert InvalidPath("Path start mismatch");
        }
        if (path[path.length - 1] != expectedEnd) {
            revert InvalidPath("Path end mismatch");
        }

        // Ensure no duplicate tokens in path
        for (uint i = 0; i < path.length - 1; i++) {
            for (uint j = i + 1; j < path.length; j++) {
                if (path[i] == path[j]) {
                    revert InvalidPath("Duplicate token in path");
                }
            }
        }
    }

    /**
     * @notice Simulate arbitrage profit without executing
     * @param params Arbitrage parameters
     * @return expectedProfit Expected profit from the arbitrage
     */
    function simulateArbitrage(ArbitrageParams calldata params)
        external
        view
        returns (uint256 expectedProfit)
    {
        // Determine buy path
        address[] memory buyPath;
        if (params.buyPath.length > 0) {
            buyPath = params.buyPath;
        } else {
            buyPath = new address[](2);
            buyPath[0] = params.tokenBorrow;
            buyPath[1] = params.tokenTarget;
        }

        // Get buy price
        uint256[] memory buyAmounts = IUniswapV2Router(params.buyDex).getAmountsOut(
            params.amount,
            buyPath
        );
        uint256 targetAmount = buyAmounts[buyAmounts.length - 1];

        // Determine sell path
        address[] memory sellPath;
        if (params.sellPath.length > 0) {
            sellPath = params.sellPath;
        } else {
            sellPath = new address[](2);
            sellPath[0] = params.tokenTarget;
            sellPath[1] = params.tokenBorrow;
        }

        // Get sell price
        uint256[] memory sellAmounts = IUniswapV2Router(params.sellDex).getAmountsOut(
            targetAmount,
            sellPath
        );
        uint256 finalAmount = sellAmounts[sellAmounts.length - 1];

        // Calculate profit (accounting for 0.09% Aave flashloan fee)
        uint256 flashloanFee = (params.amount * 9) / 10000; // 0.09%
        uint256 totalCost = params.amount + flashloanFee;

        if (finalAmount > totalCost) {
            expectedProfit = finalAmount - totalCost;
        } else {
            expectedProfit = 0;
        }

        return expectedProfit;
    }

    /**
     * @notice Withdraw profits to owner
     * @param token Token address to withdraw
     */
    function withdrawProfit(address token) external onlyOwner {
        uint256 balance = IERC20(token).balanceOf(address(this));
        require(balance > 0, "No balance");

        IERC20(token).safeTransfer(owner(), balance);

        emit ProfitWithdrawn(token, balance, owner());
    }

    /**
     * @notice Withdraw ETH (if any)
     */
    function withdrawETH() external onlyOwner {
        uint256 balance = address(this).balance;
        require(balance > 0, "No ETH balance");

        (bool success, ) = owner().call{value: balance}("");
        require(success, "ETH transfer failed");
    }

    /**
     * @notice Emergency token rescue
     * @param token Token to rescue
     * @param amount Amount to rescue
     */
    function rescueTokens(address token, uint256 amount) external onlyOwner {
        IERC20(token).safeTransfer(owner(), amount);
    }

    /**
     * @notice Get Aave Pool address
     */
    function ADDRESSES_PROVIDER() external view returns (address) {
        return address(POOL);
    }

    /**
     * @notice Pause contract in emergency
     * @dev Only owner can pause
     */
    function pause() external onlyOwner {
        _pause();
    }

    /**
     * @notice Unpause contract
     * @dev Only owner can unpause
     */
    function unpause() external onlyOwner {
        _unpause();
    }

    /**
     * @notice Set maximum trade size
     * @param newMaxSize New maximum trade size in wei
     */
    function setMaxTradeSize(uint256 newMaxSize) external onlyOwner {
        uint256 oldSize = maxTradeSize;
        maxTradeSize = newMaxSize;
        emit MaxTradeSizeUpdated(oldSize, newMaxSize);
    }

    /**
     * @notice Set minimum profit threshold
     * @param newThreshold New minimum profit threshold in wei
     */
    function setMinProfitThreshold(uint256 newThreshold) external onlyOwner {
        uint256 oldThreshold = minProfitThreshold;
        minProfitThreshold = newThreshold;
        emit MinProfitThresholdUpdated(oldThreshold, newThreshold);
    }

    /**
     * @notice Receive function to accept ETH
     */
    receive() external payable {}
}
