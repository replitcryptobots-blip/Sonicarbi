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
        address tokenTarget;      // Token to swap to
        address buyDex;           // DEX to buy on (router address)
        address sellDex;          // DEX to sell on (router address)
        uint256 minProfit;        // Minimum profit in tokenBorrow
        uint256 deadline;         // Transaction deadline
        uint256 slippageBps;      // Maximum slippage in basis points (e.g., 200 = 2%)
    }

    /// @notice Maximum allowed slippage (5% in basis points)
    uint256 public constant MAX_SLIPPAGE_BPS = 500;

    /// @notice Events
    event ArbitrageExecuted(
        address indexed tokenBorrow,
        address indexed tokenTarget,
        uint256 amountBorrowed,
        uint256 profit,
        address buyDex,
        address sellDex
    );

    event ProfitWithdrawn(address indexed token, uint256 amount, address indexed to);

    /// @notice Errors
    error InsufficientProfit(uint256 actual, uint256 required);
    error UnauthorizedFlashLoan();
    error ArbitrageFailed(string reason);

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
        require(params.amount > 0, "Invalid amount");
        require(params.buyDex != address(0), "Invalid buy DEX");
        require(params.sellDex != address(0), "Invalid sell DEX");
        require(params.buyDex != params.sellDex, "Same DEX");
        require(params.deadline >= block.timestamp, "Deadline passed");
        require(params.slippageBps <= MAX_SLIPPAGE_BPS, "Slippage too high");

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

        // Approve the Pool to pull the total debt
        IERC20(asset).safeIncreaseAllowance(address(POOL), totalDebt);

        emit ArbitrageExecuted(
            arbParams.tokenBorrow,
            arbParams.tokenTarget,
            amount,
            netProfit,
            arbParams.buyDex,
            arbParams.sellDex
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
        // Step 1: Swap tokenBorrow -> tokenTarget on buyDex (with slippage protection)
        uint256 targetAmount = _swapOnDex(
            params.buyDex,
            params.tokenBorrow,
            params.tokenTarget,
            amount,
            params.deadline,
            params.slippageBps
        );

        // Step 2: Swap tokenTarget -> tokenBorrow on sellDex (with slippage protection)
        uint256 finalAmount = _swapOnDex(
            params.sellDex,
            params.tokenTarget,
            params.tokenBorrow,
            targetAmount,
            params.deadline,
            params.slippageBps
        );

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

        return amounts[amounts.length - 1];
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
        // Get buy price
        address[] memory buyPath = new address[](2);
        buyPath[0] = params.tokenBorrow;
        buyPath[1] = params.tokenTarget;

        uint256[] memory buyAmounts = IUniswapV2Router(params.buyDex).getAmountsOut(
            params.amount,
            buyPath
        );

        uint256 targetAmount = buyAmounts[1];

        // Get sell price
        address[] memory sellPath = new address[](2);
        sellPath[0] = params.tokenTarget;
        sellPath[1] = params.tokenBorrow;

        uint256[] memory sellAmounts = IUniswapV2Router(params.sellDex).getAmountsOut(
            targetAmount,
            sellPath
        );

        uint256 finalAmount = sellAmounts[1];

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
     * @notice Receive function to accept ETH
     */
    receive() external payable {}
}
